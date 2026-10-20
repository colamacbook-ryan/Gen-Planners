"""Hàng đợi job: chạy core agent cho một dự án, rồi build + check + export để trình xem hiển thị.

billing = owner    → chạy bằng agent profile (tài khoản của owner), tính vào quota job/tháng của user.
billing = user_key → chạy bằng API key của chính user (Anthropic → claude CLI, Gemini → agy chế độ API key), HOME tạm riêng job.
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time

from . import agents, db, interview, ssot
from .config import JOBS_HOME, ROOT, WORKSPACE, which
from .security import dec

GEN = [sys.executable, str(ROOT / "gen.py")]
EXPORT = [sys.executable, str(ROOT / "tools" / "export.py")]
PROMPT = (ROOT / "pipeline" / "core-agent-prompt.md").read_text()
_running: dict[int, subprocess.Popen] = {}
STATUS_VI = {"needs_login": "chưa đăng nhập", "quota_exhausted": "có vẻ hết quota"}


def log(job_id, text):
    db.append_log(job_id, text if text.endswith("\n") else text + "\n")


def base_env():
    return {**os.environ, "GP_PROJECTS": str(WORKSPACE), "PYTHONUNBUFFERED": "1"}


def sh(job_id, cmd, env=None, cwd=None, timeout=600):
    log(job_id, "$ " + " ".join(str(c) for c in cmd[:6]) + (" …" if len(cmd) > 6 else ""))
    r = subprocess.run(cmd, env=env or base_env(), cwd=cwd or ROOT, capture_output=True, text=True, timeout=timeout)
    out = (r.stdout + r.stderr).strip()
    if out:
        log(job_id, out[-6000:])
    return r.returncode, out


def ensure_project(job_id, p):
    d = WORKSPACE / p["slug"]
    if not d.exists():
        sh(job_id, [*GEN, "new", p["slug"], "--name", p["name"]])
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
    b = which(engine)
    if not b:
        raise RuntimeError(f"Chưa cài {engine} trên máy chủ (admin → Core agent → Cài đặt CLI).")
    if engine == "agy":
        cmd = [b, "-p", prompt, "--output-format", "stream-json", "--dangerously-skip-permissions",
               "--print-timeout", f"{timeout_min}m", "--add-dir", str(project_dir)]
    else:
        cmd = [b, "-p", prompt, "--output-format", "stream-json", "--verbose", "--add-dir", str(project_dir),
               "--allowedTools", "Bash,Read,Edit,Write,Glob,Grep,WebSearch,WebFetch,Task"]
    return cmd + (["--model", model] if model else [])


def run_agent(job, engine, env, model, project_dir, p):
    timeout_min = int(db.setting("job_timeout_min", "120"))
    prompt = PROMPT.format(root=ROOT, project_dir=project_dir, slug=p["slug"], country=p.get("country") or "Việt Nam",
                           projects_root=WORKSPACE)
    env = {**env, "GP_PROJECTS": str(WORKSPACE), "PYTHONUNBUFFERED": "1"}
    proc = subprocess.Popen(agent_cmd(engine, prompt, model, timeout_min, project_dir), env=env, cwd=str(ROOT),
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            start_new_session=True)
    _running[job["id"]] = proc
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
        if time.time() - t0 > timeout_min * 60 + 120:
            log(job["id"], "⏱ quá thời gian — dừng agent")
            os.killpg(proc.pid, signal.SIGTERM)
    proc.wait()
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


def post_build(jid, p, link_check=True):
    """build + check + export (+ kiểm link nguồn). Trả (ok, số lỗi check)."""
    bcode, _ = sh(jid, [*GEN, "build", p["slug"]])
    ccode, cout = sh(jid, [*GEN, "check", p["slug"]])
    sh(jid, [*EXPORT, p["slug"], "--media-base", f"/api/projects/{p['slug']}/media"])
    if link_check and bcode == 0:
        log(jid, "Kiểm tra link nguồn…")
        try:
            r = ssot.link_check(p["slug"])
            log(jid, f"✓ {r['ok']}/{r['checked']} link mở được · {r['blocked']} bị chặn bot · {len(r['broken'])} hỏng")
        except Exception as e:  # noqa: BLE001 — kiểm link lỗi không làm hỏng job
            log(jid, f"(bỏ qua kiểm link: {e})")
    return bcode == 0, cout.count("ERROR")


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
        elif engine != "demo":
            profile = db.one("SELECT * FROM agent_profiles WHERE id=?", (job["profile_id"],))
            engine = profile["engine"]
            env = agents.env_for(profile, agents.home(profile))
            log(jid, f"Engine {engine} · tài khoản hệ thống \"{profile['name']}\" · model {job['model'] or profile['model'] or 'mặc định'}")
        if engine == "demo":
            log(jid, "Engine demo: không gọi AI — chỉ ghi idea/brief vào dự án và build từ template để thử luồng.")
            code, tail = 0, ""
        else:
            code, usage, tail = run_agent(job, engine, env, job["model"] or (profile or {}).get("model"), d, p)
            if usage:
                db.insert("usage", user_id=job["user_id"], project_id=p["id"], source="job",
                          provider="owner:" + engine if profile else "user:" + engine, model=job["model"] or (profile or {}).get("model"),
                          profile_id=profile["id"] if profile else None, input_tokens=usage["input_tokens"],
                          output_tokens=usage["output_tokens"], cost_usd=usage.get("cost_usd"), created=db.now())
                db.update("jobs", jid, usage=json.dumps(usage, ensure_ascii=False))
            if db.one("SELECT status FROM jobs WHERE id=?", (jid,))["status"] == "cancelled":
                return finish(jid, "cancelled", "Đã huỷ", p)
            if code != 0:
                reason = ("needs_login" if agents.AUTH_HINT.search(tail) else
                          "quota_exhausted" if agents.QUOTA_HINT.search(tail) else None)
                if profile and reason:
                    db.update("agent_profiles", profile["id"], status=reason)
                    nxt = agents.active_profile(exclude=(profile["id"],))
                    if nxt and db.setting("auto_failover") == "1" and job["attempt"] < 3:
                        log(jid, f"⚠ Tài khoản \"{profile['name']}\" {STATUS_VI[reason]} → chuyển sang \"{nxt['name']}\" và chạy lại.")
                        db.update("jobs", jid, status="queued", profile_id=nxt["id"], attempt=job["attempt"] + 1)
                        return
                    return finish(jid, "failed", f"Tài khoản agent {STATUS_VI[reason]} — báo owner (admin → Core agent)", p)
                return finish(jid, "failed", f"Agent thoát mã {code}", p)
        ok, errors = post_build(jid, p, link_check=engine != "demo")
        if not ok:
            return finish(jid, "failed", "Build lỗi", p)
        finish(jid, "done", f"check: {errors} lỗi" if errors else None, p)
    except Exception as e:  # noqa: BLE001 — mọi lỗi phải hiện trong log job
        log(jid, f"✗ {type(e).__name__}: {e}")
        finish(jid, "failed", str(e)[:500], db.one("SELECT * FROM projects WHERE id=?", (job.get("project_id"),)))
    finally:
        h = JOBS_HOME / str(jid)
        if h.exists():
            shutil.rmtree(h, ignore_errors=True)            # HOME tạm có key của user — xoá ngay


def finish(jid, status, error=None, p=None):
    db.update("jobs", jid, status=status, error=error, finished=db.now(), pid=None)
    log(jid, f"— kết thúc: {status}" + (f" ({error})" if error else ""))
    if p:
        db.update("projects", p["id"], status={"done": "done", "cancelled": "ready"}.get(status, "failed"), updated=db.now())


def cancel(jid):
    db.update("jobs", jid, status="cancelled")
    proc = _running.get(jid)
    if proc and proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass


def loop():
    db.x("UPDATE jobs SET status='failed', error='Máy chủ khởi động lại khi job đang chạy' WHERE status='running'")
    active: dict[int, threading.Thread] = {}
    while True:
        for k in [k for k, t in active.items() if not t.is_alive()]:
            active.pop(k)
        if len(active) < int(db.setting("max_concurrent_jobs", "1")):
            j = db.one("SELECT * FROM jobs WHERE status='queued' ORDER BY id LIMIT 1")
            if j:
                db.update("jobs", j["id"], status="starting")
                t = threading.Thread(target=run_job, args=(j,), daemon=True)
                active[j["id"]] = t
                t.start()
        time.sleep(1)


def start():
    threading.Thread(target=loop, daemon=True, name="gp-worker").start()
