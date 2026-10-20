"""Thao tác trên SSOT của một dự án trong workspace: sửa giả định, kiểm link nguồn, đóng gói, đọc tiến độ stage.

Sửa giả định = sửa đúng một dòng `value:` trong assumptions.yaml (giữ comment và định dạng), đúng luật SSOT số 4.
"""
import concurrent.futures as cf
import io
import json
import re
import zipfile
from pathlib import Path

import httpx
import yaml

from .config import WORKSPACE


class SSOTError(Exception):
    pass


def project_dir(slug: str) -> Path:
    return WORKSPACE / slug


def load(p: Path):
    return yaml.safe_load(p.read_text()) or {} if p.exists() else {}


# ------------------------------------------------------------------ giả định
def read_assumptions(slug):
    d = project_dir(slug)
    A = load(d / "assumptions.yaml")
    meta = A.get("meta", {})
    rows = [{"id": k, "label": v.get("label") or k, "value": v.get("value"), "unit": v.get("unit"), "status": v.get("status"),
             "confidence": v.get("confidence"), "source": v.get("source") or [], "note": v.get("note")}
            for k, v in (A.get("assumptions") or {}).items() if isinstance(v, dict)]
    return {"meta": {"start_year": meta.get("start_year"), "years": meta.get("years"), "unit_label": meta.get("unit_label")}, "assumptions": rows}


def _fmt(v):
    if isinstance(v, list):
        return "[" + ", ".join(_fmt(x) for x in v) + "]"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return json.dumps(v) if isinstance(v, str) else str(v)


def _coerce(new, old):
    """Giá trị mới phải cùng hình dạng với giá trị cũ: số ↔ số, list ↔ list cùng độ dài."""
    def num(x):
        if isinstance(x, bool) or not isinstance(x, (int, float, str)):
            raise SSOTError("Giá trị phải là số")
        try:
            f = float(str(x).replace(",", ".").strip())
        except ValueError:
            raise SSOTError(f"Không đọc được số: {x}") from None
        return int(f) if f.is_integer() else f
    if isinstance(old, list):
        items = new if isinstance(new, list) else [s for s in re.split(r"[;\s]+", str(new).strip()) if s]
        if len(items) != len(old):
            raise SSOTError(f"Cần đúng {len(old)} giá trị (mỗi năm một số)")
        return [num(x) for x in items]
    if isinstance(old, (int, float)) and not isinstance(old, bool):
        return num(new)
    raise SSOTError("Giả định này không phải số — sửa trực tiếp trong assumptions.yaml")


def set_value(slug, key, new, status=None):
    p = project_dir(slug) / "assumptions.yaml"
    A = load(p)
    cur = (A.get("assumptions") or {}).get(key)
    if not isinstance(cur, dict):
        raise SSOTError(f"Không có giả định {key}")
    old = cur.get("value")
    value = _coerce(new, old)
    if status and status not in ("placeholder", "estimate", "verified"):
        raise SSOTError("Trạng thái không hợp lệ")
    if status == "verified" and not cur.get("source"):
        raise SSOTError("Chỉ đánh 'verified' khi giả định có nguồn trong evidence.yaml")
    lines = p.read_text().split("\n")
    head = re.compile(rf"^(\s+){re.escape(key)}:\s*\{{")
    done = False
    for i, line in enumerate(lines):
        if head.match(line):
            new_line = re.sub(r"(\bvalue:\s*)(\[[^\]]*\]|[^,}]+)", lambda m: m.group(1) + _fmt(value), line, count=1)
            if status:
                new_line = re.sub(r"(\bstatus:\s*)([^,}]+)", lambda m: m.group(1) + status, new_line, count=1)
            lines[i], done = new_line, True
            break
    if done:
        text = "\n".join(lines)
        check = yaml.safe_load(text)["assumptions"][key]           # chắc chắn sửa dòng xong vẫn là YAML đúng
        if check.get("value") != value:
            raise SSOTError("Sửa dòng thất bại — kiểm tra định dạng assumptions.yaml")
        p.write_text(text)
    else:                                                         # giả định viết dạng khối nhiều dòng: ghi lại cả file
        cur["value"] = value
        if status:
            cur["status"] = status
        p.write_text(yaml.safe_dump(A, allow_unicode=True, sort_keys=False))
    return {"id": key, "label": cur.get("label") or key, "old": old, "value": value}


def kpi(slug):
    f = project_dir(slug) / "build" / "export" / "project.json"
    return json.loads(f.read_text()).get("kpi") if f.exists() else None


# ------------------------------------------------------------------ kiểm tra link nguồn
def collect_urls(slug):
    d = project_dir(slug)
    found = {}

    def walk(x, where):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in ("url", "link", "href") and isinstance(v, str) and v.startswith("http"):
                    found.setdefault(v, {"url": v, "where": where, "title": x.get("title") or x.get("name") or ""})
                else:
                    walk(v, where)
        elif isinstance(x, list):
            for v in x:
                walk(v, where)
    for name in ("evidence.yaml", "story.yaml", "products.yaml"):
        walk(load(d / name), name)
    return list(found.values())


def _probe(client, url):
    try:
        r = client.head(url)
        if r.status_code in (403, 405, 400, 404) or r.status_code >= 500:   # nhiều site không trả lời HEAD đúng
            r = client.get(url, headers={"Range": "bytes=0-2048"})
        code = r.status_code
        return {"code": code, "ok": code < 400, "blocked": code in (401, 403, 429)}
    except httpx.HTTPError as e:
        return {"code": None, "ok": False, "blocked": False, "error": type(e).__name__}


def link_check(slug, workers=12):
    items = collect_urls(slug)
    headers = {"User-Agent": "Mozilla/5.0 (GenPlanner link-check)"}
    with httpx.Client(timeout=12, follow_redirects=True, headers=headers) as client, cf.ThreadPoolExecutor(workers) as ex:
        for it, res in zip(items, ex.map(lambda i: _probe(client, i["url"]), items)):
            it.update(res)
    out = {"checked": len(items), "ok": sum(i["ok"] for i in items), "blocked": sum(i["blocked"] for i in items),
           "broken": [i for i in items if not i["ok"] and not i["blocked"]], "items": items}
    f = project_dir(slug) / "build" / "linkcheck.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(out, ensure_ascii=False))
    return out


def link_summary(slug):
    f = project_dir(slug) / "build" / "linkcheck.json"
    if not f.exists():
        return None
    j = json.loads(f.read_text())
    return {k: j[k] for k in ("checked", "ok", "blocked")} | {"broken": j["broken"][:30]}


# ------------------------------------------------------------------ đóng gói & tiến độ
BUNDLE_FILES = ["idea.md", "brief.md", "project.yaml", "assumptions.yaml", "evidence.yaml", "story.yaml", "datasets.yaml",
                "products.yaml", "deck.md"]
BUNDLE_DIRS = ["sections", "research", "media"]
BUILD_FILES = ["business-plan.docx", "deck.pptx", "financials.xlsx", "business-plan.md"]


def bundle(slug) -> bytes:
    d = project_dir(slug)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in BUILD_FILES:
            if (d / "build" / f).exists():
                z.write(d / "build" / f, f"{slug}/{f}")
        for f in BUNDLE_FILES:
            if (d / f).exists():
                z.write(d / f, f"{slug}/ssot/{f}")
        for sub in BUNDLE_DIRS:
            for f in sorted((d / sub).rglob("*")) if (d / sub).exists() else []:
                if f.is_file():
                    z.write(f, f"{slug}/ssot/{f.relative_to(d)}")
        z.writestr(f"{slug}/README.txt", "Thư mục gốc: tài liệu đã build (Word, PowerPoint, Excel, Markdown).\n"
                   "ssot/: nguồn số liệu duy nhất — sửa assumptions.yaml rồi chạy `python gen.py build <slug>` "
                   "trong repo Gen-Planners để dựng lại toàn bộ.\n")
    return buf.getvalue()


def stage_progress(slug):
    p = load(project_dir(slug) / "project.yaml").get("stages") or {}
    return {"done": sum(1 for v in p.values() if v == "done"), "total": len(p)} if p else None
