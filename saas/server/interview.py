"""Phòng phỏng vấn founder, phòng brainstorm và biên dịch brief.md.

Nguồn câu hỏi: pipeline/interview.yaml (một phần của chuẩn dự án). Mọi lượt chat chạy bằng API key của chính user;
không có key thì dùng chế độ demo (kịch bản cố định) nếu owner cho phép.
"""
import json

import yaml

from . import db, llm
from .config import ROOT
from .security import dec

BANK = yaml.safe_load((ROOT / "pipeline" / "interview.yaml").read_text())
QUESTIONS = BANK["questions"]
QIDS = [x["id"] for x in QUESTIONS]
QMAP = {x["id"]: x for x in QUESTIONS}
BLOCKS = {b["id"]: b["title"] for b in BANK["blocks"]}
CATEGORIES = ["product", "customer", "channel", "revenue", "ops", "team", "risk", "roadmap", "other"]


class NoKey(Exception):
    pass


# ------------------------------------------------------------------ helpers
def assistant_for(user_id):
    """Key mặc định của user → (provider, key, model, key_id). Không có key → demo (nếu được phép)."""
    k = db.one("SELECT * FROM api_keys WHERE user_id=? ORDER BY is_default DESC, id DESC LIMIT 1", (user_id,))
    if k:
        return k["provider"], dec(k["key_enc"]), k["model"] or (llm.PROVIDERS[k["provider"]]["models"] or [""])[0], k["id"]
    if db.setting("allow_demo_engine") == "1":
        return "demo", "", "demo", None
    raise NoKey("Chưa có API key. Vào Cài đặt → API key để thêm key của bạn.")


def state(pid):
    s = db.one("SELECT * FROM interview WHERE project_id=?", (pid,))
    if not s:
        db.x("INSERT INTO interview(project_id, answers, current_qid) VALUES(?,?,?)", (pid, "{}", QIDS[0]))
        s = db.one("SELECT * FROM interview WHERE project_id=?", (pid,))
    s["answers"] = json.loads(s["answers"] or "{}")
    return s


def save_state(pid, answers, current, done):
    db.x("UPDATE interview SET answers=?, current_qid=?, done=? WHERE project_id=?",
         (json.dumps(answers, ensure_ascii=False), current, int(done), pid))


def progress(answers):
    req = [q for q in QIDS if QMAP[q].get("required")]
    return {"answered": sum(1 for q in QIDS if answers.get(q)), "total": len(QIDS),
            "required_missing": [q for q in req if not answers.get(q)]}


def next_unanswered(answers, after=None):
    order = QIDS[QIDS.index(after) + 1:] + QIDS if after in QIDS else QIDS
    return next((q for q in order if not answers.get(q)), None)


def ask_text(qid):
    q = QMAP[qid]
    return f"**{BLOCKS[q['block']]} · câu {QIDS.index(qid) + 1}/{len(QIDS)}** — {q['ask']}"


def history(pid, room, limit=24):
    rows = db.q("SELECT role, content FROM messages WHERE project_id=? AND room=? ORDER BY id DESC LIMIT ?", (pid, room, limit))
    msgs = [{"role": r["role"], "content": r["content"]} for r in reversed(rows) if r["role"] in ("user", "assistant")]
    while msgs and msgs[0]["role"] != "user":       # API yêu cầu lượt đầu là user
        msgs.pop(0)
    return msgs


def add_msg(pid, room, role, content, meta=None):
    return db.insert("messages", project_id=pid, room=room, role=role, content=content,
                     meta=json.dumps(meta, ensure_ascii=False) if meta else None, created=db.now())


def _call(user_id, pid, system, msgs):
    provider, key, model, key_id = assistant_for(user_id)
    if provider == "demo":
        return None, provider
    text, usage = llm.chat(provider, key, model, system, msgs)
    db.insert("usage", user_id=user_id, project_id=pid, source="chat", provider=provider, model=model,
              input_tokens=usage["input_tokens"], output_tokens=usage["output_tokens"], created=db.now())
    return llm.parse_json(text), provider


# ------------------------------------------------------------------ interview
def start_interview(p):
    st = state(p["id"])
    intro = (f"Chào anh/chị — tôi là trợ lý phỏng vấn của **{p['name']}**. Tôi sẽ hỏi {len(QIDS)} câu ngắn theo "
             f"{len(BLOCKS)} chủ đề để hiểu đúng ý tưởng gốc trước khi agent nghiên cứu. Câu nào chưa biết, cứ nói \"chưa biết\" — "
             "agent sẽ nghiên cứu sau.\n\n" + ask_text(st["current_qid"]))
    add_msg(p["id"], "interview", "assistant", intro, {"qid": st["current_qid"]})


def interview_turn(p, user_id, text):
    pid = p["id"]
    st = state(pid)
    answers, cur = st["answers"], st["current_qid"]
    add_msg(pid, "interview", "user", text, {"qid": cur})
    sysmsg = (
        "Bạn là chuyên gia phỏng vấn founder (venture analyst cấp cao). Mục tiêu: hiểu đúng ý tưởng gốc để agent nghiên cứu sau đó.\n"
        "Quy tắc:\n- " + "\n- ".join(BANK["style"]) + "\n\n"
        f"Ý tưởng gốc:\n{p['idea']}\n\n"
        "Danh sách câu hỏi (id | chủ đề | câu hỏi | probes | đã trả lời):\n" +
        "\n".join(f"{q['id']} | {BLOCKS[q['block']]} | {q['ask']} | {'; '.join(q.get('probes', []))} | "
                  f"{answers.get(q['id']) or '—'}" for q in QUESTIONS) +
        f"\n\nCâu đang hỏi: {cur}.\n"
        "Trả về DUY NHẤT một JSON: {\"captured\": {\"<id>\": \"tóm tắt câu trả lời bằng lời của founder, giữ nguyên tên gọi và con số\"}, "
        "\"next_qid\": \"<id câu sẽ hỏi tiếp, hoặc giữ id hiện tại nếu cần probe>\", \"reply\": \"lời nói tiếp theo với founder "
        "(ghi nhận ngắn + một câu hỏi)\", \"done\": false}. Founder trả lời luôn cho câu khác thì capture cả câu đó. "
        "Khi mọi câu đã có trả lời: done=true và reply tóm tắt 5 dòng."
    )
    out, provider = _call(user_id, pid, sysmsg, history(pid, "interview"))
    if out is None:                                  # demo: ghi nguyên văn, sang câu tiếp
        if cur:
            answers[cur] = text.strip()
        nxt = next_unanswered(answers, cur)
        reply = "Đã ghi nhận." + (f"\n\n{ask_text(nxt)}" if nxt else
                                  "\n\nĐã đủ các câu. Mở tab **Brief** để xem bản tổng hợp, hoặc sang **Brainstorm** để chốt các điểm quan trọng.")
        out = {"captured": {cur: text.strip()} if cur else {}, "next_qid": nxt, "reply": reply, "done": nxt is None}
    for k, v in (out.get("captured") or {}).items():
        if k in QMAP and str(v).strip():
            answers[k] = str(v).strip()
    nxt = out.get("next_qid") if out.get("next_qid") in QMAP else next_unanswered(answers, cur)
    done = bool(out.get("done")) or nxt is None
    save_state(pid, answers, nxt, done)
    reply = out.get("reply") or (ask_text(nxt) if nxt else "Đã đủ thông tin.")
    add_msg(pid, "interview", "assistant", reply, {"qid": nxt, "provider": provider})
    db.update("projects", pid, updated=db.now())
    return {"reply": reply, "progress": progress(answers), "current_qid": nxt, "done": done}


# ------------------------------------------------------------------ brainstorm
def brainstorm_turn(p, user_id, text):
    pid = p["id"]
    mid = add_msg(pid, "brainstorm", "user", text)
    dec_rows = db.q("SELECT id,title,detail,category,status FROM decisions WHERE project_id=? AND status!='rejected'", (pid,))
    answers = state(pid)["answers"]
    sysmsg = (
        "Bạn là cố vấn chiến lược cấp cao, cùng founder brainstorm để CHỐT DẦN các điểm quan trọng của dự án.\n"
        "Tôn trọng ý tưởng gốc và các mại điểm founder giữ (must_keep); đề xuất mạnh lên, không thay hướng. "
        "Nói thẳng trade-off, hỏi lại khi thiếu dữ kiện, không bịa số liệu hay nguồn — số nào chưa có nguồn thì nói rõ là giả định.\n\n"
        f"Ý tưởng gốc:\n{p['idea']}\n\nTrả lời phỏng vấn:\n" +
        "\n".join(f"- {QMAP[k]['ask']} → {v}" for k, v in answers.items() if k in QMAP) +
        "\n\nCác điểm (status: proposed/locked):\n" +
        ("\n".join(f"- #{d['id']} [{d['status']}] ({d['category']}) {d['title']}: {d['detail'] or ''}" for d in dec_rows) or "- chưa có") +
        "\n\nTrả về DUY NHẤT một JSON: {\"reply\": \"câu trả lời markdown, ngắn gọn, có lập luận\", "
        "\"proposals\": [{\"title\": \"điểm cần chốt, ≤ 12 từ\", \"detail\": \"1–3 câu: nội dung + vì sao\", "
        f"\"category\": \"một trong {CATEGORIES}\"}}]}}. Chỉ đưa proposal khi thật sự có điểm đáng chốt (0–3 cái), không lặp điểm đã có."
    )
    out, provider = _call(user_id, pid, sysmsg, history(pid, "brainstorm"))
    if out is None:
        out = {"reply": "(Chế độ demo — chưa có API key) Tôi ghi ý này thành một điểm đề xuất để anh/chị chốt hoặc loại. "
                        "Thêm API key ở Cài đặt để có cố vấn AI thật phản biện và đề xuất.",
               "proposals": [{"title": text.strip()[:80], "detail": text.strip(), "category": "other"}] if len(text.strip()) > 15 else []}
    created = []
    for pr in (out.get("proposals") or [])[:3]:
        if not str(pr.get("title", "")).strip():
            continue
        cat = pr.get("category") if pr.get("category") in CATEGORIES else "other"
        did = db.insert("decisions", project_id=pid, title=str(pr["title"]).strip()[:200], detail=str(pr.get("detail", "")).strip(),
                        category=cat, status="proposed", source_msg=mid, created=db.now(), updated=db.now())
        created.append(did)
    reply = out.get("reply") or "…"
    add_msg(pid, "brainstorm", "assistant", reply, {"proposals": created, "provider": provider})
    db.update("projects", pid, updated=db.now())
    return {"reply": reply, "proposals": created}


# ------------------------------------------------------------------ brief
def build_brief(p):
    pid = p["id"]
    answers = state(pid)["answers"]
    decs = db.q("SELECT * FROM decisions WHERE project_id=? ORDER BY category, id", (pid,))
    L = [f"# Brief — {p['name']}", "",
         "> Biên dịch tự động từ phòng phỏng vấn + phòng brainstorm. Đây là neo **founder-first**: agent phải giữ ý tưởng gốc "
         "và các điểm đã chốt làm trung tâm; đề xuất khác chỉ ghi ở mục \"Phương án khác\".", "",
         f"Thị trường mục tiêu: {p.get('country') or 'Việt Nam'}", "", "## Ý tưởng gốc (nguyên văn)", "", p["idea"] or "", "",
         "## Phỏng vấn founder", ""]
    for bid, title in BLOCKS.items():
        qs = [q for q in QUESTIONS if q["block"] == bid and answers.get(q["id"])]
        if qs:
            L += [f"### {title}", ""] + [f"- **{q['ask']}**  \n  {answers[q['id']]}" for q in qs] + [""]
    locked = [d for d in decs if d["status"] == "locked"]
    L += ["## Các điểm đã chốt", ""] + ([f"- **[{d['category']}] {d['title']}** — {d['detail'] or ''}" for d in locked] or ["- (chưa có)"]) + [""]
    rej = [d for d in decs if d["status"] == "rejected"]
    if rej:
        L += ["## Hướng đã loại (không đi theo)", ""] + [f"- {d['title']}" for d in rej] + [""]
    pend = [d for d in decs if d["status"] == "proposed"]
    open_q = [q for q in QUESTIONS if not answers.get(q["id"])]
    L += ["## Câu hỏi mở — agent nghiên cứu hoặc ghi là giả định", ""]
    L += [f"- {q['ask']}{' (bắt buộc)' if q.get('required') else ''}" for q in open_q]
    L += [f"- Điểm chưa chốt: {d['title']}" for d in pend]
    if not open_q and not pend:
        L.append("- (không có)")
    md = "\n".join(L) + "\n"
    db.update("projects", pid, brief_md=md, updated=db.now())
    return md
