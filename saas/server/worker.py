"""Hàng đợi job: chạy core agent cho một dự án, rồi build + check + export để trình xem hiển thị.

billing = owner    → chạy bằng agent profile (tài khoản của owner), tính vào quota job/tháng của user.
billing = user_key → chạy bằng API key của chính user (Anthropic → claude CLI, Gemini → agy chế độ API key), HOME tạm riêng job.
"""
import datetime as dt
import json
import re
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import agents, db, history, interview, sandbox, ssot
from .config import HISTORY, JOBS_HOME, ROOT, WORKSPACE
from .security import dec

GEN = [sys.executable, str(ROOT / "gen.py")]
EXPORT = [sys.executable, str(ROOT / "tools" / "export.py")]
PROMPT = (ROOT / "pipeline" / "core-agent-prompt.md").read_text()
EXTERNAL_PROMPT = (ROOT / "pipeline" / "external-agent-prompt.md").read_text()
_running: dict[int, subprocess.Popen] = {}
STATUS_VI = {"needs_login": "chưa đăng nhập", "quota_exhausted": "có vẻ hết quota"}


def log(job_id, text):
    db.append_log(job_id, text if text.endswith("\n") else text + "\n")


def base_env():
    """Môi trường cho gen.py/export.py: không mang bí mật của máy chủ (nội dung dự án do người dùng/agent viết)."""
    return {**sandbox.clean_env(dict(os.environ)), "GP_PROJECTS": str(WORKSPACE), "GP_HISTORY": str(HISTORY), "PYTHONUNBUFFERED": "1",
            "GP_RENDER_MEM_MB": os.environ.get("GP_RENDER_MEM_MB", "2048")}


def sh(job_id, cmd, env=None, cwd=None, timeout=600):
    log(job_id, scrub("$ " + " ".join(str(c) for c in cmd[:6]) + (" …" if len(cmd) > 6 else "")))
    r = subprocess.run(cmd, env=env or base_env(), cwd=cwd or ROOT, capture_output=True, text=True, timeout=timeout)
    out = scrub((r.stdout + r.stderr).strip())
    if out:
        log(job_id, out[-6000:])
    return r.returncode, out


def scrub(text):
    """Không lộ đường dẫn máy chủ trong log người dùng đọc."""
    for path, label in ((str(WORKSPACE) + "/", ""), (str(ROOT) + "/", ""), (sys.executable, "python")):
        text = text.replace(path, label)
    return text


def ensure_project(job_id, p):
    d = WORKSPACE / p["slug"]
    if not d.exists():
        sh(job_id, [*GEN, "new", p["slug"], "--name", p["name"]])
        sandbox.private(d)                       # 700 ngay từ đầu: agent của job khác không đọc được dù đoán ra slug
        history.ensure(p["slug"])
    (d / "idea.md").write_text("# Ý tưởng gốc\n\n" + (p["idea"] or "") + "\n")
    (d / "brief.md").write_text(p.get("brief_md") or interview.build_brief(p))
    return d


# ------------------------------------------------------------------ parse agent stream
def summarize(ev):
    t = ev.get("type", "")
    msg = ev.get("message") if isinstance(ev.get("message"), dict) else {}
    for c in msg.get("content", []) if isinstance(msg.get("content"), list) else []:
        if c.get("type") == "text" and c.get("text", "").strip():
            return "› " + c["text"].strip()[:400]
        if c.get("type") == "tool_use":
            inp = c.get("input", {})
            return f"⚙ {c.get('name')} {str(inp.get('command') or inp.get('file_path') or inp.get('query') or inp.get('url') or '')[:160]}"
    if t == "result" or "response" in ev:
        return "✓ " + str(ev.get("result") or ev.get("response") or ev.get("status") or "")[:1500]
    for k in ("text", "content", "delta", "message"):
        if isinstance(ev.get(k), str) and ev[k].strip():
            return f"· {ev[k].strip()[:300]}"
    return None


def norm_usage(ev):
    u = ev.get("usage") or ev.get("usageMetadata")
    if not isinstance(u, dict):
        return None
    inp = sum(v for k, v in u.items() if isinstance(v, (int, float)) and ("input" in k.lower() or "prompt" in k.lower()))
    out = sum(v for k, v in u.items() if isinstance(v, (int, float)) and ("output" in k.lower() or "candidates" in k.lower()))
    return {"input_tokens": int(inp), "output_tokens": int(out), "cost_usd": ev.get("total_cost_usd"), "raw": u}


def agent_cmd(engine, prompt, model, timeout_min, project_dir):
    b, found = agents.agent_binary(engine)
    if not b:
        raise RuntimeError(agents.cli_problem(engine) if found else f"Chưa cài {engine} trên máy chủ (admin → Core agent → Cài đặt CLI).")
    if engine == "agy":
        cmd = [b, "-p", prompt, "--output-format", "stream-json", "--dangerously-skip-permissions",
               "--print-timeout", f"{timeout_min}m", "--add-dir", str(project_dir)]
    else:
        cmd = [b, "-p", prompt, "--output-format", "stream-json", "--verbose", "--add-dir", str(project_dir),
               "--allowedTools", "Bash,Read,Edit,Write,Glob,Grep,WebSearch,WebFetch,Task"]
    return cmd + (["--model", model] if model else [])


def run_agent(job, engine, env, model, project_dir, p):
    timeout_min = db.setting_int("job_timeout_min", 120)
    prompt = PROMPT.format(root=ROOT, project_dir=project_dir, slug=p["slug"], country=p.get("country") or "Việt Nam",
                           projects_root=WORKSPACE)
    env = {**env, "GP_PROJECTS": str(WORKSPACE), "PYTHONUNBUFFERED": "1"}
    if db.one("SELECT status FROM jobs WHERE id=?", (job["id"],))["status"] == "cancelled":   # huỷ trước khi agent kịp khởi động
        return -1, None, "cancelled"
    proc = subprocess.Popen(agent_cmd(engine, prompt, model, timeout_min, project_dir), env=env, cwd=str(project_dir),
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            start_new_session=True, **sandbox.popen_kwargs())
    _running[job["id"]] = proc
    deadline = threading.Timer(timeout_min * 60 + 120, lambda: (log(job["id"], "⏱ quá thời gian — dừng agent"), stop(proc)))
    deadline.daemon = True
    deadline.start()                                                  # dừng cả khi agent treo không in gì
    db.update("jobs", job["id"], pid=proc.pid)
    threading.Thread(target=watch_progress, args=(job["id"], p["slug"], proc), daemon=True).start()
    usage, tail, t0 = None, [], time.time()
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        tail = (tail + [line])[-40:]
        try:
            ev = json.loads(line)
            usage = norm_usage(ev) or usage
            s = summarize(ev)
            if s:
                log(job["id"], s)
        except json.JSONDecodeError:
            log(job["id"], line[:500])
    proc.wait()
    deadline.cancel()
    _running.pop(job["id"], None)
    return proc.returncode, usage, "\n".join(tail)


def watch_progress(jid, slug, proc):
    """Agent đánh dấu stage done trong project.yaml — đọc định kỳ để UI hiện tiến độ."""
    last = None
    while proc.poll() is None:
        pr = ssot.stage_progress(slug)
        if pr and pr != last:
            db.update("jobs", jid, progress=json.dumps(pr))
            last = pr
        time.sleep(5)


def save_version(jid, p):
    """Lưu phiên bản SSOT TRƯỚC khi build — mã phiên bản in trên hồ sơ khớp đúng phiên bản này."""
    j = db.one("SELECT j.kind, j.engine, u.email FROM jobs j LEFT JOIN users u ON u.id=j.user_id WHERE j.id=?", (jid,))
    msg = j and VERSION_MSG.get(j["kind"])
    if not msg:
        return
    try:
        rev = history.commit(p["slug"], ("Agent ngoài nộp bài" if j["engine"] == "external" else msg.format(engine=j["engine"])) + f" — job #{jid}", j["email"])
        if rev:
            log(jid, f"Đã lưu phiên bản {rev}")
    except Exception as e:  # noqa: BLE001 — lịch sử lỗi không làm hỏng job
        log(jid, scrub(f"(không lưu được phiên bản: {e})"))


def post_build(jid, p, link_check=True):
    """build + check + export (+ kiểm link nguồn). Trả (ok, số lỗi check)."""
    sandbox.strip_links(WORKSPACE / p["slug"])
    save_version(jid, p)
    bcode, _ = sh(jid, [*GEN, "build", p["slug"]])
    ccode, cout = sh(jid, [*GEN, "check", p["slug"]])
    ecode, _ = sh(jid, [*EXPORT, p["slug"], "--media-base", f"/api/projects/{p['slug']}/media"])
    if ecode != 0:
        log(jid, "✗ Xuất dữ liệu console lỗi — xem dòng lỗi phía trên (thường do YAML sai kiểu)")
        return False, cout.count("ERROR")
    if link_check and bcode == 0:
        log(jid, "Kiểm tra link nguồn…")
        try:
            r = ssot.link_check(p["slug"])
            log(jid, f"✓ {r['ok']}/{r['checked']} link mở được · {r['blocked']} bị chặn bot · {len(r['broken'])} hỏng")
        except Exception as e:  # noqa: BLE001 — kiểm link lỗi không làm hỏng job
            log(jid, f"(bỏ qua kiểm link: {e})")
    return bcode == 0, cout.count("ERROR")


def export_check(slug):
    """build + check + export như lúc nộp bài — để agent ngoài thấy mọi lỗi TRƯỚC khi nộp."""
    out, errors = [], 0
    sandbox.strip_links(WORKSPACE / slug)
    for cmd in ([*GEN, "build", slug], [*GEN, "check", slug], [*EXPORT, slug, "--media-base", f"/api/projects/{slug}/media"]):
        r = subprocess.run(cmd, env=base_env(), cwd=ROOT, capture_output=True, text=True, timeout=300)
        text = scrub((r.stdout + r.stderr).strip())
        out.append(text)
        errors += text.count("ERROR") + (1 if r.returncode != 0 and "ERROR" not in text else 0)
    return {"errors": errors, "output": "\n".join(out)[-8000:]}


def free_tier_daily(tail):
    """Key Gemini gói miễn phí hết lượt/ngày: nói thẳng là gói không đủ chạy Plan, không chỉ 'có vẻ hết quota'."""
    m = re.search(r"free_tier\w*, limit: (\d+), model: ([\w.-]+)", tail)
    if not m or "PerDay" not in tail:
        return None
    wait = re.search(r"retry in (\d+)h", tail)
    return (f"Key Gemini đang ở gói miễn phí: chỉ {m[1]} lượt gọi/ngày cho {m[2]}"
            f"{f' (mở lại sau khoảng {wait[1]} giờ)' if wait else ''} — một lần Chạy Plan cần hàng trăm lượt. "
            "Bật thanh toán (billing) cho project Google Cloud của key, hoặc dùng tài khoản agy đăng nhập Google.")


# ------------------------------------------------------------------ main job
def run_job(job):
    jid = job["id"]
    db.update("jobs", jid, status="running", started=db.now())
    try:
        if job["kind"] == "install":
            code, _ = sh(jid, ["bash", "-lc", agents.ENGINES[job["engine"]]["install"]], timeout=900)
            return finish(jid, "done" if code == 0 else "failed", None if code == 0 else f"exit {code}")
        p = db.one("SELECT * FROM projects WHERE id=?", (job["project_id"],))
        if job["kind"] in ("rebuild", "linkcheck"):
            if job["kind"] == "linkcheck":
                r = ssot.link_check(p["slug"])
                log(jid, f"✓ {r['ok']}/{r['checked']} link mở được · {r['blocked']} bị chặn bot · {len(r['broken'])} hỏng")
                for b in r["broken"][:20]:
                    log(jid, f"  ✗ {b.get('code') or b.get('error')}  {b['url']}")
                return finish(jid, "done")
            ok, errors = post_build(jid, p, link_check=False)
            return finish(jid, "done" if ok else "failed", None if ok else "Build lỗi", p)
        d = ensure_project(jid, p)
        db.update("projects", p["id"], status="running", updated=db.now())
        usage, engine, profile = None, job["engine"], None
        if job["billing"] == "user_key":
            k = db.one("SELECT * FROM api_keys WHERE id=?", (job["api_key_id"],))
            engine = {"anthropic": "claude", "gemini": "agy"}[k["provider"]]
            h = JOBS_HOME / str(jid)
            h.mkdir(parents=True, exist_ok=True)
            fake = {"engine": engine, "auth_mode": "api_key"}
            env = agents.env_for(fake, h, dec(k["key_enc"]))
            log(jid, f"Engine {engine} · API key của user ({k['provider']} {k['key_hint']}) · model {job['model'] or 'mặc định'}")
        elif engine not in ("demo", "external"):
            profile = db.one("SELECT * FROM agent_profiles WHERE id=?", (job["profile_id"],))
            engine = profile["engine"]
            env = agents.env_for(profile, agents.home(profile))
            log(jid, f"Engine {engine} · tài khoản hệ thống \"{profile['name']}\" · model {job['model'] or profile['model'] or 'mặc định'}")
        if engine == "external":
            base = db.setting("public_base_url") or "http://localhost:8080"
            db.update("jobs", jid, status="waiting")
            log(jid, f"Đang chờ agent ngoài nhận việc — bản giao việc: GET {base.rstrip('/')}/api/jobs/{jid}/handoff (kèm API token của bạn).")
            return                                                    # agent nộp bài bằng POST /api/jobs/{id}/complete
        if engine == "demo":
            log(jid, "Engine demo: không gọi AI — chỉ ghi idea/brief vào dự án và build từ template để thử luồng.")
            code, tail = 0, ""
        else:
            home_dir = Path(env["HOME"])
            if sandbox.agent_ids() and sandbox.problem():
                return finish(jid, "failed", sandbox.problem(), p, system=True)
            sandbox.grant(d, home_dir)
            try:
                code, usage, tail = run_agent(job, engine, env, job["model"] or (profile or {}).get("model"), d, p)
            finally:
                sandbox.revoke(d, home_dir)
                gone = sandbox.strip_links(d)
                if gone:
                    log(jid, f"Đã xoá {len(gone)} symlink/file đặc biệt agent tạo: {', '.join(gone[:5])}")
            if usage:
                db.insert("usage", user_id=job["user_id"], project_id=p["id"], source="job",
                          provider="owner:" + engine if profile else "user:" + engine, model=job["model"] or (profile or {}).get("model"),
                          profile_id=profile["id"] if profile else None, input_tokens=usage["input_tokens"],
                          output_tokens=usage["output_tokens"], cost_usd=usage.get("cost_usd"), created=db.now())
                db.update("jobs", jid, usage=json.dumps(usage, ensure_ascii=False))
            if db.one("SELECT status FROM jobs WHERE id=?", (jid,))["status"] == "cancelled":
                return finish(jid, "cancelled", "Đã huỷ", p)
            if code != 0:
                if "free_tier" in tail and "limit: 0" in tail:               # không phải hết quota tạm thời: model không có trong gói
                    return finish(jid, "failed", "Key Gemini đang ở gói miễn phí, model này có hạn mức 0 — chọn model Flash "
                                                 "(ví dụ gemini-3.8-flash-medium) cho tài khoản agent rồi chạy lại.", p, system=True)
                reason = ("needs_login" if agents.AUTH_HINT.search(tail) else
                          "quota_exhausted" if agents.QUOTA_HINT.search(tail) else None)
                if profile and reason:
                    db.update("agent_profiles", profile["id"], status=reason)
                    nxt = agents.active_profile(exclude=(profile["id"],))
                    if nxt and db.setting("auto_failover") == "1" and job["attempt"] < 3:
                        log(jid, f"⚠ Tài khoản \"{profile['name']}\" {STATUS_VI[reason]} → chuyển sang \"{nxt['name']}\" và chạy lại.")
                        db.update("jobs", jid, status="queued", profile_id=nxt["id"], attempt=job["attempt"] + 1)
                        return
                    return finish(jid, "failed", free_tier_daily(tail) or f"Tài khoản agent {STATUS_VI[reason]} — báo owner (admin → Core agent)", p,
                                  system=True)
                return finish(jid, "failed", f"Agent thoát mã {code}", p)
        ok, errors = post_build(jid, p, link_check=engine != "demo")
        if not ok:
            return finish(jid, "failed", "Build lỗi", p)
        finish(jid, "done", f"check: {errors} lỗi" if errors else None, p)
    except Exception as e:  # noqa: BLE001 — mọi lỗi phải hiện trong log job
        log(jid, f"✗ {type(e).__name__}: {e}")
        finish(jid, "failed", str(e)[:500], db.one("SELECT * FROM projects WHERE id=?", (job.get("project_id"),)), system=True)
    finally:
        h = JOBS_HOME / str(jid)
        if h.exists():
            shutil.rmtree(h, ignore_errors=True)            # HOME tạm có key của user — xoá ngay


def stop(proc, grace=10):
    """SIGTERM cả nhóm tiến trình, sau `grace` giây vẫn còn thì SIGKILL."""
    for sig in (signal.SIGTERM, signal.SIGKILL):
        if proc.poll() is not None:
            return
        try:
            os.killpg(proc.pid, sig)
        except (ProcessLookupError, PermissionError):
            return
        try:
            proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            continue


def handoff_text(jid, p, base):
    return EXTERNAL_PROMPT.format(base=base.rstrip("/"), slug=p["slug"], job=jid, country=p.get("country") or "Việt Nam")


def finalize_external(jid, summary=""):
    """Agent ngoài nộp bài: build + check + export + kiểm link, như sau một lần chạy agent nội bộ."""
    j = db.one("SELECT * FROM jobs WHERE id=?", (jid,))
    p = db.one("SELECT * FROM projects WHERE id=?", (j["project_id"],))
    db.update("jobs", jid, status="running")
    if summary:
        log(jid, "✓ Agent nộp bài: " + summary[:3000])
    try:
        ok, errors = post_build(jid, p)
        finish(jid, "done" if ok else "failed", (f"check: {errors} lỗi" if errors else None) if ok else "Build lỗi", p)
    except Exception as e:  # noqa: BLE001
        log(jid, f"✗ {type(e).__name__}: {e}")
        finish(jid, "failed", str(e)[:500], p)


VERSION_MSG = {"plan": "Chạy Plan ({engine})", "rebuild": "Build lại sau khi sửa số liệu", "linkcheck": None}


def finish(jid, status, error=None, p=None, system=False):
    """system=True: lỗi phía hệ thống (không phải do người dùng) — không trừ hạn mức lần chạy của họ."""
    if status != "cancelled" and db.one("SELECT status FROM jobs WHERE id=?", (jid,))["status"] == "cancelled":
        status, error = "cancelled", "Đã huỷ"                       # người dùng huỷ trong lúc build — không ghi đè

    db.update("jobs", jid, status=status, error=error, finished=db.now(), pid=None, system_fault=int(system))
    log(jid, f"— kết thúc: {status}" + (f" ({error})" if error else ""))
    if p:
        db.update("projects", p["id"], status={"done": "done", "cancelled": "ready"}.get(status, "failed"), updated=db.now())


def cancel(jid):
    db.update("jobs", jid, status="cancelled", error="Đã huỷ", finished=db.now())
    j = db.one("SELECT project_id FROM jobs WHERE id=?", (jid,))
    if j and j["project_id"]:                                         # dự án thôi "đang chạy" ngay, không đợi tiến trình dừng hẳn
        db.x("UPDATE projects SET status='ready', updated=? WHERE id=? AND status='running'", (db.now(), j["project_id"]))
    proc = _running.get(jid)
    if proc and proc.poll() is None:
        threading.Thread(target=stop, args=(proc,), daemon=True).start()


def _ours(pid):
    """PID còn sống VÀ đúng là agent của chính máy chủ này (PID có thể đã bị tái dùng sau khi máy khởi động lại)."""
    try:
        env = Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
    except OSError:
        return False
    return f"GP_PROJECTS={WORKSPACE}".encode() in env


def kill_orphan(pid):
    """Agent sống sót sau khi máy chủ chết (start_new_session) vẫn tiêu quota và ghi vào dự án — dừng cả nhóm tiến trình."""
    if not pid or not _ours(pid):
        return False
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(pid, sig)
        except (ProcessLookupError, PermissionError):
            return True
        for _ in range(50):
            if not _ours(pid):
                return True
            time.sleep(0.1)
    return True


def recover():
    """Job đang chạy khi máy chủ tắt thì không thể tiếp tục — dừng agent mồ côi, đánh dấu lỗi để người dùng chạy lại."""
    for j in db.q("SELECT id, project_id, pid FROM jobs WHERE status IN ('running','starting')"):
        killed = kill_orphan(j["pid"])
        log(j["id"], "✗ Máy chủ khởi động lại khi job đang chạy" + (" — đã dừng agent còn sót" if killed else "") + ". Bấm chạy lại.")
        db.update("jobs", j["id"], status="failed", error="Máy chủ khởi động lại khi job đang chạy — bấm chạy lại", finished=db.now(),
                  pid=None, system_fault=1)
        if j["project_id"]:
            db.update("projects", j["project_id"], status="failed", updated=db.now())


def prune_logs():
    """Chính sách lưu log (Cài đặt → Vận hành): xoá nội dung log job đã xong lâu hơn N ngày, giữ dòng job cho thống kê."""
    days = db.setting_int("log_retention_days", 0)
    if days <= 0:
        return
    cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).replace(microsecond=0).isoformat()
    db.x("UPDATE jobs SET log=? WHERE finished IS NOT NULL AND finished < ? AND log NOT LIKE '(log đã xoá%'",
         (f"(log đã xoá theo chính sách lưu {days} ngày)", cutoff))


def loop():
    recover()
    active: dict[int, threading.Thread] = {}
    last_prune = 0.0
    while True:
        if time.time() - last_prune > 3600:
            last_prune = time.time()
            try:
                prune_logs()
            except Exception as e:  # noqa: BLE001 — dọn log lỗi không được làm dừng hàng đợi
                print("prune_logs:", e)
        for k in [k for k, t in active.items() if not t.is_alive()]:
            active.pop(k)
        if len(active) < max(1, db.setting_int("max_concurrent_jobs", 1)):
            j = db.one("SELECT * FROM jobs WHERE status='queued' ORDER BY id LIMIT 1")
            if j and db.claim(j["id"]):                                  # nhận job nguyên tử — không bao giờ chạy trùng
                t = threading.Thread(target=run_job, args=(j,), daemon=True)
                active[j["id"]] = t
                t.start()
        time.sleep(1)


_started = threading.Lock()
_started_flag = []


def start():
    """Chỉ một vòng worker mỗi tiến trình (startup có thể chạy lại nhiều lần, ví dụ trong test)."""
    with _started:
        if _started_flag:
            return
        _started_flag.append(True)
    threading.Thread(target=loop, daemon=True, name="gp-worker").start()
