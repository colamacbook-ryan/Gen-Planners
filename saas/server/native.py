"""Engine native: agent nghiên cứu chạy bằng API key LLM của chính người dùng (DeepSeek, OpenAI, Gemini, Anthropic, OpenRouter).

Khác core agent CLI (agy / Claude Code — tài khoản gói tháng của owner): engine này gọi thẳng API bằng function calling chuẩn OpenAI,
không có shell. Công cụ chỉ gồm đọc chuẩn, đọc/ghi file SSOT của đúng dự án, tìm web, đọc trang, build+check, kết thúc stage —
nội dung bị prompt-injection cùng lắm chỉ ghi được SSOT của dự án đó.

Chạy lần lượt từng stage của pipeline/stages.yaml (+ stage console), mỗi stage một hội thoại mới mang theo ý tưởng, brief và ghi chú
của các stage trước — ngữ cảnh không phình mãi, chi phí có trần thật (giá × token, hoặc số OpenRouter trả về).
"""
import json
import re
import time

import yaml

from . import db, llm, search, ssot
from .config import ROOT, WORKSPACE

PROMPT = (ROOT / "pipeline" / "native-agent-prompt.md").read_text()
MAX_STEPS = 40                 # mỗi stage
KEEP_FULL = 6                  # chỉ giữ nguyên văn 6 kết quả công cụ gần nhất, cũ hơn thì rút gọn (tiết kiệm token)
URL = re.compile(r"https?://[^\s\"'<>()\[\]{}]+")
CONSOLE_STAGE = {"id": "13-console", "name": "Console, dashboard & sản phẩm", "writes": ["story.yaml", "datasets.yaml", "products.yaml"],
                 "checklist": ["Viết story.yaml theo templates/project/story.yaml (6 bước: thực trạng → lộ trình), số lấy từ model bằng Jinja.",
                               "Viết datasets.yaml (biểu đồ thị trường, đối thủ, chi phí — đúng schema trong template, mọi số có nguồn).",
                               "Viết products.yaml: sản phẩm/đối thủ tham chiếu có giá và link thật."],
                 "done_when": "run_check không còn ERROR; console có đủ 6 bước."}

TOOLS = [{"type": "function", "function": f} for f in [
    {"name": "list_files", "description": "Liệt kê file SSOT hiện có của dự án (đường dẫn + kích thước).", "parameters": {"type": "object", "properties": {}}},
    {"name": "read_file", "description": "Đọc một file của dự án (idea.md, brief.md, assumptions.yaml, sections/02-market.md…).",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "read_standard", "description": "Đọc file chuẩn của hệ thống: AGENTS.md, pipeline/playbook.yaml, pipeline/stages.yaml, "
     "pipeline/model-reference.md, templates/project/{story,datasets,products,assumptions}.yaml, templates/project/deck.md.",
     "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    {"name": "write_file", "description": "Tạo mới hoặc ghi đè cả file SSOT. YAML được kiểm cú pháp.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
    {"name": "edit_file", "description": "Thay đúng một đoạn trong file (old phải xuất hiện đúng 1 lần). Dùng cho sửa nhỏ.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old": {"type": "string"}, "new": {"type": "string"}},
                    "required": ["path", "old", "new"]}},
    {"name": "web_search", "description": "Tìm web; trả tiêu đề, URL, trích đoạn.",
     "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "fetch_url", "description": "Đọc nội dung chữ của một trang web (đã bỏ thẻ HTML, cắt ~12.000 ký tự).",
     "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
    {"name": "run_check", "description": "Build + kiểm tra toàn bộ hồ sơ (gen.py build/check + xuất console). Trả số lỗi và các dòng ERROR/warn.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "finish_stage", "description": "Kết thúc stage hiện tại: tóm tắt điều đã làm, điều còn là ước tính, việc cần người thật làm.",
     "parameters": {"type": "object", "properties": {"summary": {"type": "string"}, "done": {"type": "boolean", "description": "false nếu chưa đạt done_when"}},
                    "required": ["summary"]}},
]]


class Stop(Exception):
    """Dừng cả lượt chạy: huỷ, quá thời gian, chạm trần chi phí."""


class Run:
    def __init__(self, job, project, provider, key, model, log, export_check):
        self.job, self.p, self.provider, self.key, self.model, self.log = job, project, provider, key, model, log
        self.export_check = export_check
        self.d = WORKSPACE / project["slug"]
        self.usage = {"input_tokens": 0, "cached_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "calls": 0}
        self.cost_known = True
        self.budget = job.get("budget_usd") or float(db.setting("native_default_budget_usd") or 3)
        self.token_cap = int(db.setting("native_token_cap") or 4_000_000)
        self.deadline = time.time() + db.setting_int("job_timeout_min", 120) * 60
        self.notes = []
        self.allowed = None            # file stage hiện tại được ghi (luật: mỗi stage chỉ sửa file trong `writes` của nó)
        self.seen = set()              # URL agent đã thực sự thấy qua web_search / fetch_url — chỉ được trích các URL này
        self.search_warned = False

    # ------------------------------------------------------------ giới hạn
    def guard(self):
        if db.one("SELECT status FROM jobs WHERE id=?", (self.job["id"],))["status"] == "cancelled":
            raise Stop("cancelled")
        if time.time() > self.deadline:
            raise Stop("Quá thời gian tối đa của lượt chạy")
        if self.cost_known and self.usage["cost_usd"] >= self.budget:
            raise Stop(f"budget: đã dùng {self.usage['cost_usd']:.3f} / {self.budget:g} USD")
        if self.usage["input_tokens"] + self.usage["output_tokens"] >= self.token_cap:
            raise Stop(f"budget: đã dùng {self.usage['input_tokens'] + self.usage['output_tokens']:,} token (trần {self.token_cap:,})")

    def call(self, messages):
        self.guard()
        msg, u = llm.chat_tools(self.provider, self.key, self.model, messages, TOOLS)
        for k in ("input_tokens", "cached_tokens", "output_tokens"):
            self.usage[k] += u.get(k) or 0
        self.usage["calls"] += 1
        if u.get("cost_usd") is None:
            self.cost_known = False
        else:
            self.usage["cost_usd"] += u["cost_usd"]
        return msg

    # ------------------------------------------------------------ công cụ
    def tool(self, name, a):
        try:
            if name == "list_files":
                return "\n".join(f"{f['path']}  ({f['size']} B)" for f in self.files()) or "(trống)"
            if name == "read_file":
                f = self.path(a["path"], write=False)
                return f.read_text(errors="replace")[:40000] if f.is_file() else f"Chưa có file {a['path']}"
            if name == "read_standard":
                n = str(a["name"]).lstrip("/")
                if n not in ssot.STANDARD:
                    return "Không có file chuẩn này. Có: " + ", ".join(sorted(ssot.STANDARD))
                return (ROOT / n).read_text()[:40000]
            if name == "write_file":
                return self.write(a["path"], str(a["content"]))
            if name == "edit_file":
                f = self.path(a["path"])
                cur = f.read_text() if f.is_file() else ""
                n = cur.count(str(a["old"]))
                if n != 1:
                    return f"Lỗi: đoạn old xuất hiện {n} lần trong {a['path']} (cần đúng 1) — đọc lại file rồi thử đoạn dài hơn."
                return self.write(a["path"], cur.replace(str(a["old"]), str(a["new"]), 1))
            if name == "web_search":
                rs = search.search(a["query"])
                self.seen.update(_norm(r["url"]) for r in rs)
                return "\n\n".join(f"{i + 1}. {r['title']}\n{r['url']}\n{r['snippet']}" for i, r in enumerate(rs)) or "Không có kết quả."
            if name == "fetch_url":
                out = search.fetch(str(a["url"]))
                self.seen.add(_norm(a["url"]))
                self.seen.update(_norm(u) for u in URL.findall(out[:300]))       # URL cuối sau chuyển hướng
                return out
            if name == "run_check":
                r = self.export_check(self.p["slug"])
                lines = [x for x in r["output"].splitlines() if "ERROR" in x or "warn" in x or x.startswith(("✓", "✗"))]
                return f"Số lỗi: {r['errors']}\n" + "\n".join(lines[:60])
            return f"Không có công cụ {name}"
        except search.SearchError as e:
            if name == "web_search" and not self.search_warned:         # báo người dùng một lần: hồ sơ sẽ nhiều ước tính hơn
                self.search_warned = True
                self.log(f"⚠ Tìm web lỗi — agent chỉ đọc được URL đã biết, số liệu thiếu nguồn sẽ ghi là ước tính. {e}")
            return f"Lỗi: {e}"
        except (ssot.SSOTError, OSError, KeyError, ValueError) as e:
            return f"Lỗi: {e}"

    def files(self):
        return [{"path": str(f.relative_to(self.d)), "size": f.stat().st_size} for f in sorted(self.d.rglob("*"))
                if not f.is_symlink() and f.is_file() and ssot.SSOT_PATH.match(str(f.relative_to(self.d)))]

    def path(self, rel, write=True):
        rel = str(rel).strip().lstrip("./")
        if not ssot.SSOT_PATH.match(rel):
            raise ssot.SSOTError(f"Đường dẫn {rel} không thuộc bộ SSOT (idea.md, assumptions.yaml, sections/*.md, research/*.md…)")
        if write and rel in ssot.READ_ONLY:
            raise ssot.SSOTError(f"{rel} chỉ đọc (do hệ thống biên dịch từ phỏng vấn)")
        if write and self.allowed is not None and rel not in self.allowed and not rel.startswith("research/"):
            raise ssot.SSOTError(f"Stage này chỉ được ghi: {', '.join(sorted(self.allowed))}, research/*.md — ghi chú việc cho stage sau vào finish_stage")
        return ssot.safe_path(self.p["slug"], rel)

    def write(self, rel, content):
        if len(content.encode()) > 400_000:
            return "Lỗi: file quá lớn (> 400 KB) — tách nhỏ (vd research/r2-*.md)."
        f = self.path(rel)
        old = f.read_text(errors="replace") if f.is_file() else ""
        new_urls = {_norm(u) for u in URL.findall(content)} - {_norm(u) for u in URL.findall(old)} - self.seen
        if new_urls:                     # chống bịa nguồn: chỉ trích URL đã thấy qua công cụ trong lượt chạy này
            return ("Lỗi, chưa ghi: các URL sau chưa từng xuất hiện trong kết quả web_search / fetch_url của bạn: "
                    + ", ".join(sorted(new_urls)[:5]) + ". Tìm và đọc nguồn trước; không tìm được thì bỏ URL, ghi status: estimate + note cách ước tính.")
        if len(old) > 1500 and len(content) < 0.6 * len(old):
            return (f"Lỗi, chưa ghi: {rel} đang có {len(old):,} ký tự, bản mới chỉ {len(content):,} — sẽ mất nội dung của stage trước. "
                    "Dùng edit_file để sửa/thêm từng phần (hoặc đọc lại file và giữ nguyên phần cũ).").replace(",", ".")
        if rel.endswith(".yaml"):
            try:
                yaml.safe_load(content)
            except yaml.YAMLError as e:
                return f"Lỗi YAML, chưa ghi: {str(e)[:400]}"
        f.parent.mkdir(parents=True, exist_ok=True)
        ssot.write_nofollow(f, content.encode())
        self.log(f"⚙ ghi {rel} ({len(content):,} ký tự)".replace(",", "."))
        return f"Đã ghi {rel}."

    # ------------------------------------------------------------ stage
    def stages(self):
        st = yaml.safe_load((ROOT / "pipeline" / "stages.yaml").read_text())["stages"] + [CONSOLE_STAGE]
        done = (ssot.load(self.d / "project.yaml").get("stages") or {})
        return [s for s in st if done.get(s["id"]) != "done"], len(st)

    def mark(self, sid, ok):
        f = self.d / "project.yaml"
        py = ssot.load(f)
        py.setdefault("stages", {})[sid] = "done" if ok else "partial"
        f.write_text(yaml.safe_dump(py, allow_unicode=True, sort_keys=False))
        prog = ssot.stage_progress(self.p["slug"])
        if prog:
            db.update("jobs", self.job["id"], progress=json.dumps(prog))

    def stage_brief(self, s):
        idea = (self.d / "idea.md").read_text() if (self.d / "idea.md").exists() else ""
        brief = (self.d / "brief.md").read_text() if (self.d / "brief.md").exists() else ""
        return (f"STAGE {s['id']} — {s['name']}\nFile stage này chịu trách nhiệm: {', '.join(s.get('writes', []))} (được ghi thêm research/*.md, evidence.yaml, assumptions.yaml).\n"
                f"Checklist:\n" + "\n".join(f"- {c}" for c in s.get("checklist", [])) + f"\nXong khi: {s.get('done_when', '')}\n"
                + (f"Việc AI không làm thay được (ghi vào cuối section, mục 'Việc cần người thật làm'): {s['human_gate']}\n" if s.get("human_gate") else "")
                + "\n=== idea.md ===\n" + idea[:6000] + "\n\n=== brief.md (neo founder-first) ===\n" + brief[:12000]
                + ("\n\n=== Ghi chú các stage trước ===\n" + "\n".join(self.notes[-12:]) if self.notes else "")
                + "\n\nFile hiện có: " + ", ".join(f["path"] for f in self.files()))

    def run_stage(self, s):
        system = PROMPT.format(slug=self.p["slug"], country=self.p.get("country") or "Việt Nam")
        if self.job.get("budget_usd"):
            system += f"\nNgân sách cả lượt chạy: {self.budget:g} USD — làm gọn, ưu tiên hoàn tất SSOT + check 0 lỗi."
        self.allowed = set(s.get("writes", [])) | {"evidence.yaml", "assumptions.yaml"}
        msgs = [{"role": "system", "content": system}, {"role": "user", "content": self.stage_brief(s)}]
        idle = 0
        for _ in range(MAX_STEPS):
            m = self.call(msgs)
            calls = m.get("tool_calls") or []
            am = {"role": "assistant", "content": m.get("content") or ""}
            if calls:
                am["tool_calls"] = calls                              # giữ nguyên (kể cả chữ ký suy luận Gemini trong extra_content)
            if m.get("reasoning_content") and self.provider == "deepseek":
                am["reasoning_content"] = m["reasoning_content"]      # DeepSeek chế độ suy luận cần gửi lại trong cùng lượt tool-call
            msgs.append(am)
            if (m.get("content") or "").strip():
                self.log("› " + m["content"].strip()[:400])
            if not calls:
                idle += 1
                if idle >= 2:
                    return False, (m.get("content") or "")[:600]
                msgs.append({"role": "user", "content": "Tiếp tục bằng công cụ. Khi đạt 'Xong khi', gọi run_check rồi finish_stage."})
                continue
            idle = 0
            for c in calls:
                fn = c.get("function") or {}
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                name = fn.get("name", "")
                if name == "finish_stage":
                    return bool(args.get("done", True)), str(args.get("summary", ""))[:1500]
                shown = args.get("path") or args.get("query") or args.get("url") or args.get("name") or ""
                if name not in ("write_file", "edit_file"):
                    self.log(f"⚙ {name} {str(shown)[:160]}".rstrip())
                out = self.tool(name, args)
                msgs.append({"role": "tool", "tool_call_id": c.get("id", ""), "content": out[:14000]})
            tools_msgs = [x for x in msgs if x["role"] == "tool"]
            for old in tools_msgs[:-KEEP_FULL]:                      # rút gọn kết quả công cụ cũ — giữ ngữ cảnh gọn và rẻ
                if len(old["content"]) > 400:
                    old["content"] = old["content"][:300] + "\n…[đã rút gọn — đọc lại nếu cần]"
        return False, "Hết số bước tối đa của stage."

    def run(self):
        todo, total = self.stages()
        self.log(f"Engine native · {self.provider} · model {self.model} · {len(todo)}/{total} stage cần làm · trần "
                 + (f"{self.budget:g} USD" if self.budget else "—") + f" · tìm web: {search.provider()}")
        try:
            for s in todo:
                self.log(f"— Stage {s['id']}: {s['name']}")
                ok, summary = self.run_stage(s)
                self.mark(s["id"], ok)
                self.notes.append(f"[{s['id']}] {summary}")
                self.log(("✓ " if ok else "△ ") + f"{s['id']}: {summary[:300]}")
        except Stop as e:
            return (1 if str(e) != "cancelled" else -1), str(e)
        except llm.LLMError as e:
            return 1, str(e)
        return 0, "\n".join(self.notes[-3:])


def _norm(url):
    return str(url).strip().rstrip(".,;:/").split("#")[0].lower()


def run(job, project, provider, key, model, log, export_check):
    """→ (code, usage, tail). code 0 = chạy hết các stage; 1 = dừng (lý do ở tail); -1 = huỷ."""
    r = Run(job, project, provider, key, model, log, export_check)
    code, tail = r.run()
    u = dict(r.usage)
    u["cost_usd"] = round(u["cost_usd"], 4) if r.cost_known else None
    r.log(f"Đã dùng {u['input_tokens']:,} token vào ({u['cached_tokens']:,} trúng cache) · {u['output_tokens']:,} token ra".replace(",", ".")
          + (f" · ≈ {u['cost_usd']:.3f} USD" if u["cost_usd"] is not None else " · chi phí: xem trang nhà cung cấp"))
    return code, u, tail
