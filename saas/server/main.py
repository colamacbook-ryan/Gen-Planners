"""Gen Planner SaaS — API + trang tĩnh.  Chạy:  uvicorn saas.server.main:app --port 8080  (từ thư mục gốc repo)."""
import json
import re
import secrets
import shutil
import subprocess
import sys
import time
import unicodedata
import urllib.parse
from collections import defaultdict

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse

import datetime as dt
import hashlib
import threading

from . import agents, db, history, interview, llm, sandbox, ssot, worker
from .config import COOKIE_SECURE, ROOT, SAAS, WORKSPACE
from .security import check_pw, dec, enc, hash_pw, hint, sign, unsign

app = FastAPI(title="Gen Planner", docs_url=None, redoc_url=None)
STATIC = SAAS / "static"
COOKIE = "gp_session"
_attempts: dict[str, list[float]] = defaultdict(list)


@app.on_event("startup")
def _start():
    sandbox.lock_down()
    worker.start()


@app.middleware("http")
async def csrf(request: Request, call_next):
    # Mọi lệnh ghi phải mang header X-GP (form chéo site không đặt được header tuỳ ý)
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.url.path.startswith("/api/") \
            and request.headers.get("x-gp") != "1" and not request.headers.get("authorization", "").startswith("Bearer gp_"):
        return JSONResponse({"detail": "Thiếu header X-GP"}, status_code=403)
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    return resp


# ------------------------------------------------------------------ auth helpers
def token_hash(t):
    return hashlib.sha256(t.encode()).hexdigest()


def current_user(request: Request):
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer gp_"):                              # API token cho agent ngoài (không dùng cookie → không có CSRF)
        if not any(r.fullmatch(request.url.path) for r in TOKEN_ROUTES) or request.method not in ("GET", "PUT", "POST"):
            raise HTTPException(403, "API token chỉ dùng cho các lệnh của agent ngoài (xem bản giao việc) — không dùng cho cài đặt, quản trị hay tài khoản.")
        t = db.one("SELECT * FROM api_tokens WHERE token_hash=? AND revoked=0", (token_hash(auth[7:].strip()),))
        u = db.one("SELECT * FROM users WHERE id=?", (t["user_id"],)) if t else None
        if not u or u["status"] != "active":
            return None
        if not t["last_used"] or t["last_used"][:16] != db.now()[:16]:
            db.update("api_tokens", t["id"], last_used=db.now())
        return u
    s = unsign(request.cookies.get(COOKIE, ""))
    if not s:
        return None
    u = db.one("SELECT * FROM users WHERE id=?", (s.get("uid"),))
    if not u or u["status"] != "active" or u["session_ver"] != s.get("v"):
        return None
    return u


# API token (đưa cho agent ngoài — có thể bị prompt-injection) chỉ mở đúng các lệnh trong pipeline/external-agent-prompt.md
TOKEN_ROUTES = [re.compile(x) for x in (
    r"/api/jobs/\d+(/(handoff|progress|complete))?", r"/api/standard/.+", r"/api/samples",
    r"/api/projects/[\w-]+(/(ssot(/.+)?|check|rebuild|lint|export/[\w.-]+|files/[\w.-]+|media/[\w.-]+))?")]


def need_user(request: Request):
    u = current_user(request)
    if not u:
        raise HTTPException(401, "Chưa đăng nhập")
    return u


def need_admin(u=Depends(need_user)):
    if u["role"] not in ("owner", "admin"):
        raise HTTPException(403, "Cần quyền admin")
    return u


def need_owner(u=Depends(need_user)):
    if u["role"] != "owner":
        raise HTTPException(403, "Chỉ owner hệ thống")
    return u


def login_response(u, resp=None):
    resp = resp or JSONResponse({"ok": True, "role": u["role"]})
    resp.set_cookie(COOKIE, sign({"uid": u["id"], "v": u["session_ver"]}), max_age=14 * 24 * 3600,
                    httponly=True, samesite="lax", secure=COOKIE_SECURE)
    db.update("users", u["id"], last_login=db.now())
    return resp


def public_user(u):
    return {k: u[k] for k in ("id", "email", "name", "role", "status", "created", "last_login")}


def throttle(request: Request, who="", record=True, per_account=True, ip_limit=(10, 300)):
    """Chặn dò mật khẩu: tối đa 10 lần THẤT BẠI / 5 phút cho mỗi (IP, email), và 30 / 15 phút cho mỗi email bất kể IP —
    IP có thể bị giả qua X-Forwarded-For nếu proxy cấu hình sai, giới hạn theo tài khoản thì không."""
    now = time.time()
    rules = [(f"{request.client.host if request.client else '?'}|{who}", *ip_limit)] + ([(f"*|{who}", 30, 900)] if per_account else [])
    for k, limit, window in rules:
        _attempts[k] = [t for t in _attempts[k] if now - t < window]
        if len(_attempts[k]) >= limit:
            raise HTTPException(429, f"Thử quá nhiều lần, đợi {window // 60} phút.")
    if record:
        for k, *_ in rules:
            _attempts[k].append(now)


def to_int(v, name, lo=0, hi=10**9, allow_none=True):
    if v in (None, "") and allow_none:
        return None
    try:
        n = int(str(v).strip())
    except ValueError:
        raise HTTPException(400, f"{name}: cần một số nguyên") from None
    if not lo <= n <= hi:
        raise HTTPException(400, f"{name}: cần trong khoảng {lo}–{hi}")
    return n


def valid_invite(token, email=None):
    inv = db.one("SELECT * FROM invites WHERE token=?", (token,)) if token else None
    if not inv or inv["revoked"] or inv["used_by"] or (inv["expires"] and inv["expires"] < db.now()):
        raise HTTPException(400, "Lời mời không còn hiệu lực. Xin admin gửi lời mời mới.")
    if email and inv["email"] and inv["email"].lower() != email.lower():
        raise HTTPException(400, f"Lời mời này dành cho {inv['email']}.")
    return inv


def create_user(email, name, pw=None, google_sub=None, invite=None):
    first = db.one("SELECT COUNT(*) n FROM users")["n"] == 0
    if not first and not invite and db.setting("allow_signup") != "1":
        raise HTTPException(403, "Hệ thống đang tắt đăng ký mới — cần lời mời từ admin.")
    role = "owner" if first else (invite["role"] if invite else "user")
    uid = db.insert("users", email=email, name=name or email.split("@")[0], pw_hash=hash_pw(pw) if pw else None,
                    google_sub=google_sub, role=role, status="active", created=db.now(),
                    quota_projects=invite["quota_projects"] if invite else None,
                    quota_jobs_month=invite["quota_jobs_month"] if invite else None, invited_by=invite["created_by"] if invite else None)
    if invite:
        db.update("invites", invite["id"], used_by=uid, used_at=db.now())
    db.audit(uid, "signup", email, {"role": role, "invite": invite["id"] if invite else None})
    if first:
        threading.Thread(target=ensure_sample, args=(uid,), daemon=True).start()
    return db.one("SELECT * FROM users WHERE id=?", (uid,))


async def read_limited(request: Request, limit, msg="Dữ liệu gửi lên quá lớn"):
    """Đọc body nhưng dừng ngay khi vượt `limit` — không nạp cả request lớn vào RAM rồi mới kiểm."""
    if int(request.headers.get("content-length") or 0) > limit:
        raise HTTPException(413, msg)
    buf = bytearray()
    async for chunk in request.stream():
        buf += chunk
        if len(buf) > limit:
            raise HTTPException(413, msg)
    return bytes(buf)


async def body(request: Request) -> dict:
    raw = await read_limited(request, 1024 * 1024)
    try:
        b = json.loads(raw or b"{}")
    except (json.JSONDecodeError, ValueError):
        return {}
    return b if isinstance(b, dict) else {}


# ------------------------------------------------------------------ pages
def page(name):
    return FileResponse(STATIC / name, headers={"Cache-Control": "no-store"})


@app.get("/")
def root(request: Request):
    return RedirectResponse("/app" if current_user(request) else "/login")


@app.get("/login")
def login_page():
    return page("login.html")


@app.get("/app")
def app_page(request: Request):
    return page("app.html") if current_user(request) else RedirectResponse("/login")


@app.get("/admin")
def admin_page(request: Request):
    u = current_user(request)
    if not u:
        return RedirectResponse("/login")
    return page("admin.html") if u["role"] in ("owner", "admin") else RedirectResponse("/app")


@app.get("/static/{f}")
def static(f: str):
    p = STATIC / f
    if not re.fullmatch(r"\w[\w.-]*", f) or not p.is_file():
        raise HTTPException(404)
    return FileResponse(p)


# ------------------------------------------------------------------ auth API
@app.get("/api/public")
def public(invite: str = ""):
    inv = None
    if invite:
        try:
            i = valid_invite(invite)
            inv = {"email": i["email"], "role": i["role"]}
        except HTTPException as e:
            inv = {"error": e.detail}
    return {"invite": inv, "site_name": db.setting("site_name"), "allow_signup": db.setting("allow_signup") == "1",
            "google": bool(db.setting("google_client_id")), "has_owner": db.one("SELECT COUNT(*) n FROM users")["n"] > 0}


@app.post("/api/auth/signup")
async def signup(request: Request):
    throttle(request, "signup", per_account=False, ip_limit=(40, 3600))   # cả lớp học chung một NAT vẫn đăng ký được
    b = await body(request)
    email, pw = str(b.get("email", "")).strip().lower(), str(b.get("password", ""))
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or len(pw) < 8:
        raise HTTPException(400, "Email không hợp lệ hoặc mật khẩu dưới 8 ký tự.")
    if db.one("SELECT id FROM users WHERE email=?", (email,)):
        raise HTTPException(409, "Email đã có tài khoản.")
    inv = valid_invite(str(b["invite"]), email) if b.get("invite") else None
    return login_response(await run_in_threadpool(create_user, email, b.get("name"), pw, invite=inv))   # scrypt ~70 ms CPU: không chặn event loop


DUMMY_HASH = hash_pw(secrets.token_hex(16))


@app.post("/api/auth/login")
async def login(request: Request):
    b = await body(request)
    email = str(b.get("email", "")).strip().lower()
    throttle(request, email, record=False)
    u = db.one("SELECT * FROM users WHERE email=?", (email,))
    ok = await run_in_threadpool(check_pw, str(b.get("password", "")), (u or {}).get("pw_hash") or DUMMY_HASH)  # cùng thời gian dù email không có
    if not u or not ok:
        throttle(request, email)
        raise HTTPException(401, "Sai email hoặc mật khẩu.")
    if u["status"] != "active":
        raise HTTPException(403, "Tài khoản đang bị khoá.")
    db.audit(u["id"], "login", u["email"])
    return login_response(u)


@app.post("/api/auth/logout")
def logout():
    r = JSONResponse({"ok": True})
    r.delete_cookie(COOKIE)
    return r


@app.get("/api/auth/google")
def google_start(request: Request):
    cid = db.setting("google_client_id")
    if not cid:
        raise HTTPException(404, "Chưa cấu hình Google OAuth")
    state = secrets.token_urlsafe(16)
    base = db.setting("public_base_url") or str(request.base_url).rstrip("/")
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(
        {"client_id": cid, "redirect_uri": base + "/api/auth/google/callback", "response_type": "code",
         "scope": "openid email profile", "state": state, "prompt": "select_account"})
    r = RedirectResponse(url)
    r.set_cookie("gp_oauth", state, max_age=600, httponly=True, samesite="lax", secure=COOKIE_SECURE)
    return r


@app.get("/api/auth/google/callback")
def google_cb(request: Request, code: str = "", state: str = ""):
    if not state or state != request.cookies.get("gp_oauth"):
        raise HTTPException(400, "OAuth state không khớp")
    base = db.setting("public_base_url") or str(request.base_url).rstrip("/")
    tok = httpx.post("https://oauth2.googleapis.com/token", timeout=20, data={
        "code": code, "client_id": db.setting("google_client_id"), "client_secret": dec(db.setting("google_client_secret_enc")),
        "redirect_uri": base + "/api/auth/google/callback", "grant_type": "authorization_code"}).json()
    if "access_token" not in tok:
        raise HTTPException(400, "Google từ chối: " + str(tok.get("error_description") or tok.get("error")))
    info = httpx.get("https://openidconnect.googleapis.com/v1/userinfo", timeout=20,
                     headers={"Authorization": "Bearer " + tok["access_token"]}).json()
    if not info.get("email_verified"):
        raise HTTPException(400, "Email Google chưa xác minh")
    email = info["email"].lower()
    u = db.one("SELECT * FROM users WHERE google_sub=? OR email=?", (info["sub"], email))
    if u and not u["google_sub"]:
        db.update("users", u["id"], google_sub=info["sub"])
    u = u or create_user(email, info.get("name"), google_sub=info["sub"])
    if u["status"] != "active":
        raise HTTPException(403, "Tài khoản đang bị khoá.")
    db.audit(u["id"], "login_google", email)
    return login_response(u, RedirectResponse("/app"))


@app.get("/api/me")
def me(u=Depends(need_user)):
    keys = db.one("SELECT COUNT(*) n FROM api_keys WHERE user_id=?", (u["id"],))["n"]
    return {**public_user(u), "has_keys": keys > 0, "site_name": db.setting("site_name"),
            "plan_billing": db.setting("plan_billing"), "quota": quota(u), "demo_allowed": db.setting("allow_demo_engine") == "1",
            "core_ready": agents.active_profile() is not None, "onboarding": onboarding(u, keys > 0)}


def onboarding(u, has_keys):
    """Checklist cho người mới — tính từ dữ liệu thật, không phải cờ tự đánh dấu (trừ 'đã xem mẫu')."""
    ob = json.loads(u.get("onboarding") or "{}")
    pids = [r["id"] for r in db.q("SELECT id FROM projects WHERE user_id=? AND is_sample=0", (u["id"],))]
    ph = ",".join("?" * len(pids)) or "NULL"
    interviewed = any(not interview.progress(interview.state(pid)["answers"])["required_missing"] for pid in pids)
    demo = db.setting("allow_demo_engine") == "1"
    steps = [
        ("sample", "Xem một bộ hồ sơ mẫu hoàn chỉnh", bool(ob.get("viewed_sample"))),
        ("key", "Thêm API key AI của bạn" + (" (tuỳ chọn — đang có chế độ demo)" if demo and not has_keys else ""), has_keys),
        ("project", "Tạo dự án đầu tiên", bool(pids)),
        ("interview", f"Trả lời đủ {sum(1 for q in interview.QUESTIONS if q.get('required'))} câu phỏng vấn bắt buộc", interviewed),
        ("locked", "Chốt ít nhất một điểm ở Brainstorm", bool(pids) and db.one(f"SELECT COUNT(*) n FROM decisions WHERE status='locked' AND project_id IN ({ph})", pids)["n"] > 0),
        ("plan", "Chạy Plan và xem hồ sơ", bool(pids) and db.one(f"SELECT COUNT(*) n FROM jobs WHERE kind='plan' AND status='done' AND project_id IN ({ph})", pids)["n"] > 0),
        ("share", "Gửi link hồ sơ cho nhà đầu tư", bool(pids) and db.one(f"SELECT COUNT(*) n FROM shares WHERE revoked=0 AND project_id IN ({ph})", pids)["n"] > 0),
    ]
    optional = {"key"} if demo and not has_keys else set()          # chưa có key mà vẫn dùng demo được → không chặn tiến độ
    return {"steps": [{"id": i, "title": t, "done": d, "optional": i in optional} for i, t, d in steps],
            "done": sum(d for i, _, d in steps if i not in optional), "total": len(steps) - len(optional),
            "dismissed": bool(ob.get("dismissed"))}


@app.post("/api/me/onboarding")
async def onboarding_mark(request: Request, u=Depends(need_user)):
    b = await body(request)
    ob = json.loads(u.get("onboarding") or "{}")
    for k in ("viewed_sample", "dismissed"):
        if k in b:
            ob[k] = bool(b[k])
    db.update("users", u["id"], onboarding=json.dumps(ob))
    return {"ok": True}


@app.post("/api/me/password")
async def change_pw(request: Request, u=Depends(need_user)):
    b = await body(request)
    if u["pw_hash"] and not check_pw(str(b.get("old", "")), u["pw_hash"]):
        raise HTTPException(400, "Mật khẩu cũ không đúng")
    if len(str(b.get("new", ""))) < 8:
        raise HTTPException(400, "Mật khẩu mới tối thiểu 8 ký tự")
    db.update("users", u["id"], pw_hash=hash_pw(b["new"]), session_ver=u["session_ver"] + 1)
    db.audit(u["id"], "password_change", u["email"])
    return login_response(db.one("SELECT * FROM users WHERE id=?", (u["id"],)))


def quota(u):
    month = db.now()[:7] + "-01"
    # Lần chạy bằng tài khoản hệ thống: tính khi job đã chờ/đã bắt đầu (huỷ giữa chừng vẫn tính — chống lách quota),
    # không tính lỗi do phía hệ thống (tài khoản agent hết quota / chưa đăng nhập, máy chủ khởi động lại).
    # system_fault: lỗi phía hệ thống (agent hết quota/chưa đăng nhập, key gói miễn phí, máy chủ khởi động lại);
    # by_admin: admin bấm chạy lại — không trừ vào hạn mức của người dùng.
    used_jobs = db.one("SELECT COUNT(*) n FROM jobs WHERE user_id=? AND billing='owner' AND engine!='demo' AND kind='plan' AND created>=? "
                       "AND (started IS NOT NULL OR status IN ('queued','starting')) AND system_fault=0 AND by_admin IS NULL",
                       (u["id"], month))["n"]
    projects = db.one("SELECT COUNT(*) n FROM projects WHERE user_id=? AND is_sample=0", (u["id"],))["n"]
    lim_p = u["quota_projects"] if u["quota_projects"] is not None else db.setting_int("default_quota_projects", 5)
    lim_j = u["quota_jobs_month"] if u["quota_jobs_month"] is not None else db.setting_int("default_quota_jobs_month", 3)
    unlimited = u["role"] in ("owner", "admin")
    return {"projects": projects, "projects_limit": None if unlimited else lim_p,
            "owner_jobs_month": used_jobs, "owner_jobs_limit": None if unlimited else lim_j}


# ------------------------------------------------------------------ API keys (BYOK)
@app.get("/api/providers")
def providers(u=Depends(need_user)):
    return llm.PROVIDERS


def key_row(k):
    return {k2: k[k2] for k2 in ("id", "provider", "label", "key_hint", "model", "is_default", "last_test", "last_test_ok", "created")} \
        | {"plan_engine": llm.PROVIDERS[k["provider"]]["plan_engine"]}


@app.get("/api/keys")
def keys(u=Depends(need_user)):
    return [key_row(k) for k in db.q("SELECT * FROM api_keys WHERE user_id=? ORDER BY is_default DESC, id", (u["id"],))]


@app.post("/api/keys")
async def add_key(request: Request, u=Depends(need_user)):
    b = await body(request)
    prov, key = b.get("provider"), str(b.get("key", "")).strip()
    if prov not in llm.PROVIDERS or len(key) < 10:
        raise HTTPException(400, "Provider hoặc key không hợp lệ")
    model = str(b.get("model") or (llm.PROVIDERS[prov]["models"] or [""])[0]).strip()
    if not model:
        raise HTTPException(400, "Provider này cần nhập tên model")
    try:
        await run_in_threadpool(llm.list_models, prov, key)       # hỏi thẳng nhà cung cấp, không tốn token
    except llm.LLMError as e:
        if e.status in (400, 401, 403):                           # key sai/hết hạn: không lưu — tránh trợ lý hỏng ngay sau đó
            raise HTTPException(400, f"{llm.PROVIDERS[prov]['label']} từ chối key này (HTTP {e.status}) — kiểm tra lại key rồi dán lại.") from None
    first = not db.one("SELECT id FROM api_keys WHERE user_id=?", (u["id"],))
    kid = db.insert("api_keys", user_id=u["id"], provider=prov, label=b.get("label") or llm.PROVIDERS[prov]["label"],
                    key_enc=enc(key), key_hint=hint(key), model=model, is_default=int(first), created=db.now())
    db.audit(u["id"], "api_key_add", prov)
    return key_row(db.one("SELECT * FROM api_keys WHERE id=?", (kid,)))


def my_key(u, kid):
    k = db.one("SELECT * FROM api_keys WHERE id=? AND user_id=?", (kid, u["id"]))
    if not k:
        raise HTTPException(404)
    return k


@app.patch("/api/keys/{kid}")
async def edit_key(kid: int, request: Request, u=Depends(need_user)):
    k, b = my_key(u, kid), await body(request)
    if b.get("is_default"):
        db.x("UPDATE api_keys SET is_default=0 WHERE user_id=?", (u["id"],))
        db.update("api_keys", kid, is_default=1)
    if b.get("model"):
        db.update("api_keys", kid, model=str(b["model"]).strip())
    return key_row(db.one("SELECT * FROM api_keys WHERE id=?", (k["id"],)))


@app.delete("/api/keys/{kid}")
def del_key(kid: int, u=Depends(need_user)):
    my_key(u, kid)
    db.x("DELETE FROM api_keys WHERE id=?", (kid,))
    db.audit(u["id"], "api_key_delete", kid)
    return {"ok": True}


@app.get("/api/keys/{kid}/models")
def key_models(kid: int, u=Depends(need_user)):
    k = my_key(u, kid)
    try:
        return {"models": llm.list_models(k["provider"], dec(k["key_enc"])), "current": k["model"]}
    except llm.LLMError as e:
        raise HTTPException(502, str(e))


@app.post("/api/keys/{kid}/test")
def test_key(kid: int, u=Depends(need_user)):
    k = my_key(u, kid)
    model, note = k["model"], ""
    for _ in range(2):
        try:
            text, usage = llm.chat(k["provider"], dec(k["key_enc"]), model, "Trả lời đúng một từ: OK",
                                   [{"role": "user", "content": "ping"}], max_tokens=20)
            ok, msg = True, (text.strip()[:60] or "OK") + note
            break
        except llm.LLMError as e:
            ok, msg = False, str(e)
            if not e.suggested:
                break
            note = f" · model {model} đã bị ngừng, đã chuyển sang {e.suggested}"
            model = e.suggested
            db.update("api_keys", kid, model=model)
    db.update("api_keys", kid, last_test=db.now(), last_test_ok=int(ok))
    return {"ok": ok, "message": msg}


# ------------------------------------------------------------------ projects
def slugify(name):
    s = unicodedata.normalize("NFKD", name.replace("đ", "d").replace("Đ", "D")).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:40] or "du-an"
    return f"{s}-{secrets.token_hex(2)}"


def get_project(slug, u, write=False):
    p = db.one("SELECT * FROM projects WHERE slug=?", (slug,))
    if not p:
        raise HTTPException(404, "Không có dự án")
    if p["user_id"] != u["id"] and (write or (u["role"] not in ("owner", "admin") and not p["is_sample"])):
        raise HTTPException(403, "Không phải dự án của bạn")
    if write and p["is_sample"]:
        raise HTTPException(403, "Dự án mẫu chỉ đọc — tạo dự án mới để thử.")
    return p


def project_summary(p):
    j = db.one("SELECT id,status,engine,billing,created,finished,error FROM jobs WHERE project_id=? ORDER BY id DESC LIMIT 1", (p["id"],))
    st = interview.state(p["id"])
    return {**{k: p[k] for k in ("id", "slug", "name", "country", "status", "created", "updated", "is_sample")},
            "progress": interview.progress(st["answers"]), "last_job": j,
            "exported": (WORKSPACE / p["slug"] / "build" / "export" / "project.json").exists(),
            "locked": db.one("SELECT COUNT(*) n FROM decisions WHERE project_id=? AND status='locked'", (p["id"],))["n"]}


@app.get("/api/projects")
def my_projects(u=Depends(need_user)):
    return [project_summary(p) for p in db.q("SELECT * FROM projects WHERE user_id=? AND is_sample=0 ORDER BY updated DESC", (u["id"],))]


@app.get("/api/samples")
def samples(u=Depends(need_user)):
    return [project_summary(p) for p in db.q("SELECT * FROM projects WHERE is_sample=1 ORDER BY id")]


@app.post("/api/projects")
async def new_project(request: Request, u=Depends(need_user)):
    b = await body(request)
    name, idea = str(b.get("name", "")).strip(), str(b.get("idea", "")).strip()
    if not name or len(idea) < 20:
        raise HTTPException(400, "Cần tên dự án và mô tả ý tưởng (tối thiểu vài câu).")
    qo = quota(u)
    if qo["projects_limit"] is not None and qo["projects"] >= qo["projects_limit"]:
        raise HTTPException(403, f"Đã đạt giới hạn {qo['projects_limit']} dự án của gói. Liên hệ admin để nâng.")
    slug = slugify(name)
    pid = db.insert("projects", slug=slug, user_id=u["id"], name=name, idea=idea, country=b.get("country") or "Việt Nam",
                    status="interview", created=db.now(), updated=db.now())
    p = db.one("SELECT * FROM projects WHERE id=?", (pid,))
    interview.start_interview(p)
    db.audit(u["id"], "project_create", slug)
    return project_summary(p)


@app.get("/api/projects/{slug}")
def project_detail(slug: str, u=Depends(need_user)):
    p = get_project(slug, u)
    st = interview.state(p["id"])
    return {**project_summary(p), "idea": p["idea"], "brief_md": p["brief_md"], "answers": st["answers"],
            "current_qid": st["current_qid"], "interview_done": bool(st["done"]),
            "questions": interview.QUESTIONS, "blocks": interview.BLOCKS, "categories": interview.CATEGORIES,
            "decisions": db.q("SELECT * FROM decisions WHERE project_id=? ORDER BY status='locked' DESC, id DESC", (p["id"],)),
            "jobs": db.q("SELECT id,kind,status,engine,billing,model,created,started,finished,error,usage,progress FROM jobs "
                         "WHERE project_id=? ORDER BY id DESC LIMIT 10", (p["id"],)),
            "mine": p["user_id"] == u["id"], "kpi": ssot.kpi(slug), "links": ssot.link_summary(slug),
            "shares": [share_row(r) for r in db.q("SELECT * FROM shares WHERE project_id=? AND revoked=0 ORDER BY id DESC", (p["id"],))]
            if p["user_id"] == u["id"] else [],
            "changes": db.q("SELECT key,label,old,new,created FROM changes WHERE project_id=? ORDER BY id DESC LIMIT 20", (p["id"],)),
            "has_workspace": (WORKSPACE / slug / "assumptions.yaml").exists()}


@app.patch("/api/projects/{slug}")
async def edit_project(slug: str, request: Request, u=Depends(need_user)):
    p, b = get_project(slug, u, True), await body(request)
    kw = {k: str(b[k]).strip() for k in ("name", "idea", "country") if b.get(k)}
    db.update("projects", p["id"], **kw, updated=db.now())
    return project_summary(db.one("SELECT * FROM projects WHERE id=?", (p["id"],)))


@app.delete("/api/projects/{slug}")
def delete_project(slug: str, u=Depends(need_user)):
    p = get_project(slug, u, True)
    for j in db.q("SELECT id FROM jobs WHERE project_id=? AND status IN ('queued','starting','running','waiting')", (p["id"],)):
        worker.cancel(j["id"])                                        # không để agent chạy tiếp trong thư mục sắp xoá
    for t in ("messages", "decisions", "interview", "changes", "shares"):
        db.x(f"DELETE FROM {t} WHERE project_id=?", (p["id"],))
    db.x("DELETE FROM projects WHERE id=?", (p["id"],))
    shutil.rmtree(WORKSPACE / p["slug"], ignore_errors=True)
    history.remove(p["slug"])
    db.audit(u["id"], "project_delete", slug)
    return {"ok": True}


@app.get("/api/projects/{slug}/messages")
def messages(slug: str, room: str, u=Depends(need_user)):
    p = get_project(slug, u)
    return db.q("SELECT id,role,content,meta,created FROM messages WHERE project_id=? AND room=? ORDER BY id", (p["id"], room))


def chat_guard(fn, *a):
    try:
        return fn(*a)
    except interview.NoKey as e:
        raise HTTPException(400, str(e))
    except llm.LLMError as e:
        raise HTTPException(502, str(e))


@app.post("/api/projects/{slug}/interview")
async def interview_msg(slug: str, request: Request, u=Depends(need_user)):
    p, b = get_project(slug, u, True), await body(request)
    if not str(b.get("text", "")).strip():
        raise HTTPException(400, "Trống")
    return chat_guard(interview.interview_turn, p, u["id"], str(b["text"])[:6000])


@app.put("/api/projects/{slug}/answers")
async def edit_answers(slug: str, request: Request, u=Depends(need_user)):
    p, b = get_project(slug, u, True), await body(request)
    st = interview.state(p["id"])
    for k, v in b.items():
        if k in interview.QMAP:
            if str(v).strip():
                st["answers"][k] = str(v).strip()
            else:
                st["answers"].pop(k, None)
    nxt = interview.next_unanswered(st["answers"])
    interview.save_state(p["id"], st["answers"], nxt, nxt is None)
    return {"answers": st["answers"], "progress": interview.progress(st["answers"])}


@app.post("/api/projects/{slug}/brainstorm")
async def brainstorm_msg(slug: str, request: Request, u=Depends(need_user)):
    p, b = get_project(slug, u, True), await body(request)
    if not str(b.get("text", "")).strip():
        raise HTTPException(400, "Trống")
    return chat_guard(interview.brainstorm_turn, p, u["id"], str(b["text"])[:6000])


@app.post("/api/projects/{slug}/decisions")
async def add_decision(slug: str, request: Request, u=Depends(need_user)):
    p, b = get_project(slug, u, True), await body(request)
    if not str(b.get("title", "")).strip():
        raise HTTPException(400, "Cần tiêu đề")
    did = db.insert("decisions", project_id=p["id"], title=str(b["title"]).strip()[:200], detail=str(b.get("detail", "")),
                    category=b.get("category") if b.get("category") in interview.CATEGORIES else "other",
                    status=b.get("status") if b.get("status") in ("proposed", "locked") else "locked",
                    created=db.now(), updated=db.now())
    return db.one("SELECT * FROM decisions WHERE id=?", (did,))


@app.patch("/api/decisions/{did}")
async def edit_decision(did: int, request: Request, u=Depends(need_user)):
    d = db.one("SELECT * FROM decisions WHERE id=?", (did,))
    if not d:
        raise HTTPException(404)
    p = db.one("SELECT * FROM projects WHERE id=?", (d["project_id"],))
    get_project(p["slug"], u, True)
    b = await body(request)
    kw = {k: str(b[k]) for k in ("title", "detail") if k in b}
    if b.get("status") in ("proposed", "locked", "rejected"):
        kw["status"] = b["status"]
    if b.get("category") in interview.CATEGORIES:
        kw["category"] = b["category"]
    db.update("decisions", did, **kw, updated=db.now())
    return db.one("SELECT * FROM decisions WHERE id=?", (did,))


@app.delete("/api/decisions/{did}")
def del_decision(did: int, u=Depends(need_user)):
    d = db.one("SELECT * FROM decisions WHERE id=?", (did,))
    if d:
        get_project(db.one("SELECT slug FROM projects WHERE id=?", (d["project_id"],))["slug"], u, True)
        db.x("DELETE FROM decisions WHERE id=?", (did,))
    return {"ok": True}


@app.post("/api/projects/{slug}/brief")
def make_brief(slug: str, u=Depends(need_user)):
    p = get_project(slug, u, True)
    md = interview.build_brief(p)
    db.update("projects", p["id"], status="ready" if p["status"] in ("interview", "brainstorm") else p["status"])
    return {"brief_md": md}


@app.post("/api/projects/{slug}/run")
async def run_plan(slug: str, request: Request, u=Depends(need_user)):
    p, b = get_project(slug, u, True), await body(request)
    if db.one("SELECT id FROM jobs WHERE project_id=? AND status IN ('queued','starting','running','waiting')", (p["id"],)):
        raise HTTPException(409, "Dự án đang có job chạy.")
    missing = interview.progress(interview.state(p["id"])["answers"])["required_missing"]
    if missing and not b.get("force"):
        raise HTTPException(400, "Còn câu phỏng vấn bắt buộc chưa trả lời: " + ", ".join(missing))
    interview.build_brief(p)
    billing, mode = b.get("billing", "owner"), db.setting("plan_billing")
    if billing == "external":
        jid = db.insert("jobs", project_id=p["id"], user_id=u["id"], kind="plan", status="queued", created=db.now(),
                        engine="external", billing="external")
        db.update("projects", p["id"], status="running", updated=db.now())
        db.audit(u["id"], "job_create", slug, {"job": jid, "billing": "external"})
        return {"job_id": jid}
    kw = dict(project_id=p["id"], user_id=u["id"], kind="plan", status="queued", created=db.now(), model=b.get("model") or None)
    if billing == "demo":
        if db.setting("allow_demo_engine") != "1":
            raise HTTPException(403, "Owner đã tắt engine demo")
        kw.update(engine="demo", billing="demo")
    elif billing == "user_key":
        if mode == "owner":
            raise HTTPException(403, "Hệ thống chỉ cho chạy Plan bằng tài khoản của owner.")
        k = my_key(u, b.get("api_key_id"))
        eng = llm.PROVIDERS[k["provider"]]["plan_engine"]
        if not eng:
            raise HTTPException(400, f"Key {k['provider']} chỉ dùng để chat. Chạy Plan cần key Anthropic (claude CLI) hoặc Gemini (agy).")
        kw.update(engine=eng, billing="user_key", api_key_id=k["id"], model=b.get("model") or k["model"])
    else:
        if mode == "user_key":
            raise HTTPException(403, "Hệ thống yêu cầu chạy Plan bằng API key của bạn.")
        qo = quota(u)
        if qo["owner_jobs_limit"] is not None and qo["owner_jobs_month"] >= qo["owner_jobs_limit"]:
            raise HTTPException(403, f"Hết quota {qo['owner_jobs_limit']} lần chạy/tháng bằng tài khoản hệ thống. "
                                     "Dùng API key của bạn hoặc liên hệ admin.")
        prof = agents.active_profile()
        if not prof:
            raise HTTPException(503, "Hệ thống chưa có core agent sẵn sàng. Báo owner cấu hình ở trang admin.")
        kw.update(engine=prof["engine"], billing="owner", profile_id=prof["id"])
    jid = db.insert("jobs", **kw)
    db.update("projects", p["id"], status="running", updated=db.now())
    db.audit(u["id"], "job_create", slug, {"job": jid, "billing": kw["billing"], "engine": kw["engine"]})
    return {"job_id": jid}


def get_job(jid, u, write=False):
    """Admin xem và huỷ được job của mọi người; giao việc / báo tiến độ / nộp bài chỉ chủ job."""
    j = db.one("SELECT * FROM jobs WHERE id=?", (jid,))
    if not j or (j["user_id"] != u["id"] and (write or u["role"] not in ("owner", "admin"))):
        raise HTTPException(404)
    return j


@app.get("/api/jobs/{jid}")
def job(jid: int, u=Depends(need_user)):
    j = get_job(jid, u)
    if u["role"] not in ("owner", "admin"):
        j.pop("pid", None)
    return j


@app.post("/api/jobs/{jid}/cancel")
def job_cancel(jid: int, u=Depends(need_user)):
    j = get_job(jid, u)
    if j["status"] in ("queued", "starting", "running", "waiting"):
        worker.cancel(jid)
        db.audit(u["id"], "job_cancel", jid)
    return {"ok": True}


# ------------------------------------------------------------------ viewer & files
def export_dir(slug):
    return WORKSPACE / slug / "build" / "export"


@app.get("/api/projects/{slug}/export/{part}")
def export_part(slug: str, part: str, u=Depends(need_user)):
    get_project(slug, u)
    f = export_dir(slug) / f"{part}.json"
    if part not in ("project", "dossier", "documents") or not f.exists():
        raise HTTPException(404, "Chưa có bản xuất — chạy Plan trước.")
    return FileResponse(f, media_type="application/json")


@app.get("/api/projects/{slug}/media/{name}")
def media(slug: str, name: str, u=Depends(need_user)):
    get_project(slug, u)
    return media_file(slug, name)


MEDIA_TYPES = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp", "gif": "image/gif"}


def media_file(slug, name):
    """Chỉ phục vụ ảnh raster: html/svg trong media/ (agent ghi được) sẽ thành XSS cùng origin với /admin."""
    ext = name.rsplit(".", 1)[-1].lower()
    if not re.fullmatch(r"\w[\w.-]*", name) or ext not in MEDIA_TYPES:
        raise HTTPException(404)
    try:
        f = ssot.safe_path(slug, "media/" + name)
    except ssot.SSOTError:
        raise HTTPException(404) from None
    if not f.is_file():
        raise HTTPException(404)
    return FileResponse(f, media_type=MEDIA_TYPES[ext], headers=SAFE_FILE_HEADERS)


SAFE_FILE_HEADERS = {"X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox; default-src 'none'"}

FILES = {"business-plan.docx", "deck.pptx", "financials.xlsx", "business-plan.md", "deck.md"}


@app.get("/api/projects/{slug}/files/{name}")
def files(slug: str, name: str, u=Depends(need_user)):
    get_project(slug, u)
    f = WORKSPACE / slug / "build" / name
    if name not in FILES or not f.exists():
        raise HTTPException(404, "Chưa có file — chạy Plan trước.")
    return FileResponse(f, filename=f"{slug}-{name}")


@app.get("/api/projects/{slug}/brief.md")
def brief_file(slug: str, u=Depends(need_user)):
    p = get_project(slug, u)
    return Response(p["brief_md"] or interview.build_brief(p), media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{slug}-brief.md"'})


@app.get("/viewer/{slug}")
def viewer(slug: str, request: Request):
    u = current_user(request)
    if not u:
        return RedirectResponse("/login")
    get_project(slug, u)
    html = (ROOT / "studio" / "index.html").read_text()
    inject = f'<script>window.GP={{api:"/api",project:{json.dumps(slug)}}}</script>'
    return HTMLResponse(html.replace("<script>", inject + "<script>", 1) if "<script>" in html else inject + html,
                        headers={"Cache-Control": "no-store"})


# ------------------------------------------------------------------ số liệu (what-if), build lại, kiểm link, gói tải về
def queue_job(p, u, kind):
    if db.one("SELECT id FROM jobs WHERE project_id=? AND status IN ('queued','starting','running','waiting')", (p["id"],)):
        raise HTTPException(409, "Dự án đang có job chạy — đợi xong rồi thử lại.")
    jid = db.insert("jobs", kind=kind, project_id=p["id"], user_id=u["id"], engine="local", billing="none", status="queued", created=db.now())
    db.audit(u["id"], f"job_{kind}", p["slug"], {"job": jid})
    return jid


def need_workspace(slug):
    if not (WORKSPACE / slug / "assumptions.yaml").exists():
        raise HTTPException(404, "Dự án chưa có bộ số liệu — chạy Plan trước.")


@app.get("/api/projects/{slug}/assumptions")
def assumptions(slug: str, u=Depends(need_user)):
    get_project(slug, u)
    need_workspace(slug)
    return {**ssot.read_assumptions(slug), "kpi": ssot.kpi(slug)}


@app.patch("/api/projects/{slug}/assumptions/{key}")
async def set_assumption(slug: str, key: str, request: Request, u=Depends(need_user)):
    p, b = get_project(slug, u, True), await body(request)
    return await run_in_threadpool(_set_assumption, slug, key, p, b, u)


_edit_locks = defaultdict(threading.Lock)        # sửa số liệu tuần tự theo dự án (đọc-sửa-ghi assumptions.yaml)


def _set_assumption(slug, key, p, b, u):
    with _edit_locks[slug]:
        return _set_assumption_locked(slug, key, p, b, u)


def _set_assumption_locked(slug, key, p, b, u):
    need_workspace(slug)
    if db.one("SELECT id FROM jobs WHERE project_id=? AND status IN ('queued','starting','running','waiting')", (p["id"],)):
        raise HTTPException(409, "Dự án đang có job chạy — đợi xong rồi sửa số liệu.")
    try:
        r = ssot.set_value(slug, key, b.get("value"), b.get("status"))
    except ssot.SSOTError as e:
        raise HTTPException(400, str(e))
    db.insert("changes", project_id=p["id"], user_id=u["id"], key=key, label=r["label"], old=json.dumps(r["old"]),
              new=json.dumps(r["value"]), created=db.now())
    db.update("projects", p["id"], updated=db.now())
    db.audit(u["id"], "assumption_set", slug, {"key": key, "old": r["old"], "new": r["value"]})
    history.commit(slug, f"Đổi {r['label']}: {json.dumps(r['old'], ensure_ascii=False)} → {json.dumps(r['value'], ensure_ascii=False)}", u["email"])
    return r


@app.post("/api/projects/{slug}/rebuild")
def rebuild(slug: str, u=Depends(need_user)):
    p = get_project(slug, u, True)
    need_workspace(slug)
    return {"job_id": queue_job(p, u, "rebuild")}


@app.post("/api/projects/{slug}/linkcheck")
def linkcheck(slug: str, u=Depends(need_user)):
    p = get_project(slug, u)
    if p["user_id"] != u["id"] and u["role"] != "owner":
        raise HTTPException(403, "Không phải dự án của bạn")
    need_workspace(slug)
    return {"job_id": queue_job(p, u, "linkcheck")}


@app.get("/api/projects/{slug}/bundle.zip")
def bundle(slug: str, u=Depends(need_user)):
    get_project(slug, u)
    need_workspace(slug)
    return Response(ssot.bundle(slug), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{slug}-ho-so.zip"'})


@app.get("/api/projects/{slug}/lint")
def project_lint(slug: str, u=Depends(need_user)):
    """Lỗi + cảnh báo của gen.py check (kể cả kiểm tra độ hợp lý) cho tab Số liệu."""
    get_project(slug, u)
    need_workspace(slug)
    r = subprocess.run([sys.executable, str(ROOT / "gen.py"), "check", slug, "--json"], env=worker.base_env(), cwd=ROOT,
                       capture_output=True, text=True, timeout=300)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        return {"errors": [worker.scrub((r.stderr or r.stdout)[-500:]) or "check lỗi"], "warnings": []}


@app.get("/api/projects/{slug}/history")
def project_history(slug: str, u=Depends(need_user)):
    get_project(slug, u)
    return history.log(slug)


@app.get("/api/projects/{slug}/history/{rev}")
def project_version(slug: str, rev: str, u=Depends(need_user)):
    get_project(slug, u)
    try:
        return history.show(slug, rev)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(404, f"Không có phiên bản {rev}") from e


@app.post("/api/projects/{slug}/history/{rev}/restore")
def project_restore(slug: str, rev: str, u=Depends(need_user)):
    p = get_project(slug, u, True)
    can_edit_ssot(p)
    try:
        new = history.restore(slug, rev, u["email"])
    except (ValueError, RuntimeError) as e:
        raise HTTPException(404, f"Không khôi phục được phiên bản {rev}: {e}") from e
    db.audit(u["id"], "version_restore", slug, {"rev": rev, "new": new})
    return {"rev": new, "job_id": queue_job(p, u, "rebuild")}               # dựng lại hồ sơ theo phiên bản cũ


# ------------------------------------------------------------------ link chia sẻ cho nhà đầu tư (chỉ đọc, không cần đăng nhập)
def share_row(r):
    return {k: r[k] for k in ("id", "token", "label", "created", "views", "last_view")} | {"url": f"/s/{r['token']}"}


@app.post("/api/projects/{slug}/shares")
async def create_share(slug: str, request: Request, u=Depends(need_user)):
    p, b = get_project(slug, u, True), await body(request)
    if not (export_dir(slug) / "project.json").exists():
        raise HTTPException(400, "Chưa có hồ sơ để chia sẻ — chạy Plan trước.")
    sid = db.insert("shares", project_id=p["id"], token=secrets.token_urlsafe(18),
                    label=(str(b.get("label") or "").strip() or "Link " + dt.datetime.now().strftime("%d/%m %H:%M"))[:80],
                    created_by=u["id"], created=db.now())
    db.audit(u["id"], "share_create", slug, {"share": sid})
    return share_row(db.one("SELECT * FROM shares WHERE id=?", (sid,)))


@app.delete("/api/shares/{sid}")
def revoke_share(sid: int, u=Depends(need_user)):
    r = db.one("SELECT s.*, p.user_id, p.slug FROM shares s JOIN projects p ON p.id=s.project_id WHERE s.id=?", (sid,))
    if not r or (r["user_id"] != u["id"] and u["role"] != "owner"):
        raise HTTPException(404)
    db.update("shares", sid, revoked=1)
    db.audit(u["id"], "share_revoke", r["slug"], {"share": sid})
    return {"ok": True}


def share_project(token):
    r = db.one("SELECT s.id sid, p.* FROM shares s JOIN projects p ON p.id=s.project_id WHERE s.token=? AND s.revoked=0", (token,))
    if not r:
        raise HTTPException(404, "Link chia sẻ không tồn tại hoặc đã bị thu hồi.")
    return r


@app.get("/s/{token}")
def share_page(token: str):
    p = share_project(token)
    db.x("UPDATE shares SET views=views+1, last_view=? WHERE id=?", (db.now(), p["sid"]))
    html = (ROOT / "studio" / "index.html").read_text()
    inject = f'<script>window.GP={{api:{json.dumps("/api/share/" + token)},project:{json.dumps(p["slug"])}}}</script>'
    return HTMLResponse(html.replace("<script>", inject + "<script>", 1), headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"})


@app.get("/api/share/{token}/projects/{slug}/export/{part}")
def share_export(token: str, slug: str, part: str):
    p = share_project(token)
    f = export_dir(p["slug"]) / f"{part}.json"
    if slug != p["slug"] or part not in ("project", "dossier", "documents") or not f.exists():
        raise HTTPException(404)
    text = f.read_text().replace(f"/api/projects/{slug}/media/", f"/api/share/{token}/projects/{slug}/media/")
    return Response(text, media_type="application/json")


@app.get("/api/share/{token}/projects/{slug}/media/{name}")
def share_media(token: str, slug: str, name: str):
    p = share_project(token)
    if slug != p["slug"]:
        raise HTTPException(404)
    return media_file(slug, name)


@app.get("/api/share/{token}/projects/{slug}/files/{name}")
def share_files(token: str, slug: str, name: str):
    p = share_project(token)
    f = WORKSPACE / p["slug"] / "build" / name
    if slug != p["slug"] or name not in FILES or not f.exists():
        raise HTTPException(404)
    return FileResponse(f, filename=f"{slug}-{name}")


# ------------------------------------------------------------------ API token + agent ngoài (Claude Code, Antigravity… của người dùng)
@app.get("/api/tokens")
def list_tokens(u=Depends(need_user)):
    return db.q("SELECT id, name, prefix, created, last_used FROM api_tokens WHERE user_id=? AND revoked=0 ORDER BY id DESC", (u["id"],))


@app.post("/api/tokens")
async def create_token(request: Request, u=Depends(need_user)):
    if request.headers.get("authorization"):
        raise HTTPException(403, "Token không tạo được token khác — dùng giao diện web")
    b = await body(request)
    if db.one("SELECT COUNT(*) n FROM api_tokens WHERE user_id=? AND revoked=0", (u["id"],))["n"] >= 10:
        raise HTTPException(400, "Tối đa 10 token — thu hồi bớt token cũ")
    t = "gp_" + secrets.token_urlsafe(30)
    tid = db.insert("api_tokens", user_id=u["id"], name=str(b.get("name") or "Agent ngoài")[:60], token_hash=token_hash(t),
                    prefix=t[:9] + "…", created=db.now())
    db.audit(u["id"], "token_create", tid)
    return {"id": tid, "token": t, "note": "Chỉ hiện một lần — sao chép ngay."}


@app.delete("/api/tokens/{tid}")
def revoke_token(tid: int, u=Depends(need_user)):
    db.x("UPDATE api_tokens SET revoked=1 WHERE id=? AND user_id=?", (tid, u["id"]))
    db.audit(u["id"], "token_revoke", tid)
    return {"ok": True}


STANDARD = {"AGENTS.md", "CLAUDE.md", "pipeline/model-reference.md", "pipeline/playbook.yaml", "pipeline/stages.yaml", "pipeline/interview.yaml",
            "templates/project/story.yaml", "templates/project/datasets.yaml", "templates/project/products.yaml",
            "templates/project/assumptions.yaml", "templates/project/deck.md"}
SSOT_PATH = re.compile(r"^(idea\.md|brief\.md|project\.yaml|assumptions\.yaml|evidence\.yaml|story\.yaml|datasets\.yaml|products\.yaml|deck\.md"
                       r"|(sections|research|partials)/\w[\w.-]*\.md|media/\w[\w.-]*\.(jpg|jpeg|png|webp))$")
READ_ONLY = {"brief.md"}


@app.get("/api/standard/{path:path}")
def standard(path: str, u=Depends(need_user)):
    if path not in STANDARD:
        raise HTTPException(404, "Các file chuẩn: " + ", ".join(sorted(STANDARD)))
    return Response((ROOT / path).read_text(), media_type="text/plain; charset=utf-8")


def can_edit_ssot(p):
    """Agent/founder sửa SSOT khi không có job nội bộ đang chạy (job agent ngoài đang chờ thì được)."""
    busy = db.one("SELECT id FROM jobs WHERE project_id=? AND status IN ('queued','starting','running')", (p["id"],))
    if busy:
        raise HTTPException(409, "Dự án đang có job chạy — đợi xong rồi sửa.")
    if not (WORKSPACE / p["slug"]).exists():
        raise HTTPException(404, "Dự án chưa có workspace — bấm Chạy Plan trước.")


def external_job(p, jid=None):
    q = "SELECT * FROM jobs WHERE project_id=? AND engine='external' AND status='waiting'" + (" AND id=?" if jid else "")
    j = db.one(q + " ORDER BY id DESC", (p["id"], jid) if jid else (p["id"],))
    if not j:
        raise HTTPException(409, "Không có job agent ngoài đang chờ cho dự án này — bấm Chạy Plan → Agent ngoài trước.")
    return j


@app.get("/api/jobs/{jid}/handoff")
def handoff(jid: int, request: Request, u=Depends(need_user)):
    j = get_job(jid, u, True)
    if j["engine"] != "external":
        raise HTTPException(400, "Job này không phải agent ngoài")
    p = db.one("SELECT * FROM projects WHERE id=?", (j["project_id"],))
    base = db.setting("public_base_url") or str(request.base_url).rstrip("/")
    return {"job": jid, "status": j["status"], "project": p["slug"], "prompt": worker.handoff_text(jid, p, base),
            "standard": sorted(STANDARD)}


@app.get("/api/projects/{slug}/ssot")
def ssot_list(slug: str, u=Depends(need_user)):
    get_project(slug, u)
    d = WORKSPACE / slug
    if not d.exists():
        raise HTTPException(404, "Dự án chưa có workspace — bấm Chạy Plan trước.")
    return [{"path": str(f.relative_to(d)), "size": f.stat().st_size} for f in sorted(d.rglob("*"))
            if not f.is_symlink() and f.is_file() and SSOT_PATH.match(str(f.relative_to(d)))]


@app.get("/api/projects/{slug}/ssot/{path:path}")
def ssot_read(slug: str, path: str, u=Depends(need_user)):
    get_project(slug, u)
    if not SSOT_PATH.match(path):
        raise HTTPException(404, "Không có file")
    if path.startswith("media/"):
        return media_file(slug, path[6:])
    try:
        f = ssot.safe_path(slug, path)
    except ssot.SSOTError:
        raise HTTPException(404, "Không có file") from None
    if not f.is_file():
        raise HTTPException(404, "Không có file")
    return Response(f.read_text(errors="replace"), media_type="text/plain; charset=utf-8", headers=SAFE_FILE_HEADERS)


@app.put("/api/projects/{slug}/ssot/{path:path}")
async def ssot_write(slug: str, path: str, request: Request, u=Depends(need_user)):
    p = get_project(slug, u, True)
    can_edit_ssot(p)
    if not SSOT_PATH.match(path) or path in READ_ONLY:
        raise HTTPException(400, "Đường dẫn không được phép ghi")
    data = await read_limited(request, 2 * 1024 * 1024, "File tối đa 2 MB")
    if not path.startswith("media/"):
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(400, "File văn bản phải là UTF-8") from None
        if path.endswith(".yaml"):
            try:
                import yaml
                yaml.safe_load(text)
            except yaml.YAMLError as e:
                raise HTTPException(400, f"YAML lỗi: {e}") from None
    try:
        f = ssot.safe_path(slug, path)
        f.parent.mkdir(parents=True, exist_ok=True)
        ssot.write_nofollow(f, data)
    except ssot.SSOTError as e:
        raise HTTPException(400, str(e)) from None
    db.update("projects", p["id"], updated=db.now())
    j = db.one("SELECT id FROM jobs WHERE project_id=? AND engine='external' AND status='waiting'", (p["id"],))
    if j and path == "project.yaml" and (pr := ssot.stage_progress(slug)):
        db.update("jobs", j["id"], progress=json.dumps(pr))
    if not j:
        db.insert("changes", project_id=p["id"], user_id=u["id"], key=path, label=f"Sửa file {path}", old="", new=f"{len(data)} byte", created=db.now())
        history.commit(slug, f"Sửa {path}", u["email"])
    return {"ok": True, "path": path, "size": len(data),
            "next": "Đang có job chờ: POST /check rồi /complete." if j else f"Không có job chờ: POST /check, rồi POST /api/projects/{slug}/rebuild để cập nhật hồ sơ."}


@app.post("/api/projects/{slug}/check")
def ssot_check(slug: str, u=Depends(need_user)):
    p = get_project(slug, u, True)
    can_edit_ssot(p)
    r = worker.export_check(slug)
    return {**r, "kpi": ssot.kpi(slug), "results": f"/api/projects/{slug}/export/dossier (fin = kết quả model mọi kịch bản)",
            "rendered": [f"/api/projects/{slug}/files/{f}" for f in sorted(FILES)]}


@app.post("/api/jobs/{jid}/progress")
async def job_progress(jid: int, request: Request, u=Depends(need_user)):
    j, b = get_job(jid, u, True), await body(request)
    if j["engine"] != "external" or j["status"] != "waiting":
        raise HTTPException(409, "Job không ở trạng thái chờ agent ngoài")
    worker.log(jid, "› " + str(b.get("message", ""))[:1000])
    return {"ok": True}


@app.post("/api/jobs/{jid}/complete")
async def job_complete(jid: int, request: Request, u=Depends(need_user)):
    j, b = get_job(jid, u, True), await body(request)
    if j["engine"] != "external" or j["status"] != "waiting":
        raise HTTPException(409, "Job không ở trạng thái chờ agent ngoài")
    threading.Thread(target=worker.finalize_external, args=(jid, str(b.get("summary") or "")), daemon=True).start()
    return {"ok": True, "status": "running", "poll": f"/api/jobs/{jid}",
            "after": "Nếu cần sửa sau khi nộp: PUT /ssot/<path> rồi POST /api/projects/<slug>/rebuild."}


# ------------------------------------------------------------------ admin
@app.get("/api/admin/overview")
def overview(a=Depends(need_admin)):
    month = db.now()[:7] + "-01"
    c = lambda sql, args=(): db.one(sql, args)["n"]  # noqa: E731
    days = db.q("SELECT substr(created,1,10) d, SUM(input_tokens) i, SUM(output_tokens) o, COUNT(*) n FROM usage "
                "WHERE created >= date('now','-29 day') GROUP BY d ORDER BY d")
    return {"users": c("SELECT COUNT(*) n FROM users"), "users_active_30d": c("SELECT COUNT(*) n FROM users WHERE last_login >= date('now','-30 day')"),
            "projects": c("SELECT COUNT(*) n FROM projects"), "projects_done": c("SELECT COUNT(*) n FROM projects WHERE status='done'"),
            "jobs_running": c("SELECT COUNT(*) n FROM jobs WHERE status IN ('running','starting')"),
            "jobs_queued": c("SELECT COUNT(*) n FROM jobs WHERE status='queued'"),
            "jobs_month": c("SELECT COUNT(*) n FROM jobs WHERE created>=? AND kind='plan'", (month,)),
            "jobs_failed_month": c("SELECT COUNT(*) n FROM jobs WHERE created>=? AND status='failed'", (month,)),
            "tokens_month": db.one("SELECT COALESCE(SUM(input_tokens+output_tokens),0) n FROM usage WHERE created>=?", (month,))["n"],
            "owner_tokens_month": db.one("SELECT COALESCE(SUM(input_tokens+output_tokens),0) n FROM usage WHERE created>=? AND profile_id IS NOT NULL", (month,))["n"],
            "days": days, "active_agent": (lambda a: {k: a[k] for k in ("id", "name", "engine", "auth_mode", "model", "status")} if a else None)(agents.active_profile()),
            "new_users_7d": c("SELECT COUNT(*) n FROM users WHERE created >= ?", ((dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7)).isoformat(),)),
            "funnel": funnel(), "invites_open": c("SELECT COUNT(*) n FROM invites WHERE used_by IS NULL AND revoked=0 AND (expires IS NULL OR expires > ?)", (db.now(),)),
            "recent_jobs": db.q("SELECT j.id,j.status,j.engine,j.billing,j.created,p.slug,p.name,u.email FROM jobs j LEFT JOIN projects p ON p.id=j.project_id "
                                "LEFT JOIN users u ON u.id=j.user_id ORDER BY j.id DESC LIMIT 8")}


@app.get("/api/admin/users")
def admin_users(a=Depends(need_admin)):
    out = []
    for u in db.q("SELECT * FROM users ORDER BY id"):
        tok = db.one("SELECT COALESCE(SUM(input_tokens+output_tokens),0) n FROM usage WHERE user_id=? AND created>=?", (u["id"], db.now()[:7] + "-01"))["n"]
        nkeys = db.one("SELECT COUNT(*) n FROM api_keys WHERE user_id=?", (u["id"],))["n"]
        out.append({**public_user(u), "quota": quota(u), "quota_projects": u["quota_projects"], "quota_jobs_month": u["quota_jobs_month"],
                    "keys": nkeys, "tokens_month": tok, "google": bool(u["google_sub"]),
                    "onboarding": {k: v for k, v in onboarding(u, nkeys > 0).items() if k in ("done", "total")}})
    return out


def funnel():
    """Phễu kích hoạt người dùng thường: đăng ký → có key → có dự án → phỏng vấn xong → chạy Plan xong → chia sẻ."""
    us = db.q("SELECT id FROM users WHERE role='user'")
    steps = {"signup": len(us), "key": 0, "project": 0, "plan": 0, "share": 0}
    for u in us:
        steps["key"] += db.one("SELECT COUNT(*) n FROM api_keys WHERE user_id=?", (u["id"],))["n"] > 0
        steps["project"] += db.one("SELECT COUNT(*) n FROM projects WHERE user_id=? AND is_sample=0", (u["id"],))["n"] > 0
        steps["plan"] += db.one("SELECT COUNT(*) n FROM jobs j JOIN projects p ON p.id=j.project_id WHERE j.user_id=? AND j.kind='plan' "
                                "AND j.status='done' AND p.is_sample=0", (u["id"],))["n"] > 0   # cùng tập dự án với bước "Tạo dự án"
        steps["share"] += db.one("SELECT COUNT(*) n FROM shares s JOIN projects p ON p.id=s.project_id WHERE p.user_id=? AND s.revoked=0", (u["id"],))["n"] > 0
    return steps


@app.get("/api/admin/users/{uid}")
def admin_user_detail(uid: int, a=Depends(need_admin)):
    t = db.one("SELECT * FROM users WHERE id=?", (uid,))
    if not t:
        raise HTTPException(404)
    keys = db.q("SELECT provider, model, key_hint, created, last_test_ok FROM api_keys WHERE user_id=?", (uid,))
    return {**public_user(t), "quota": quota(t), "quota_projects": t["quota_projects"], "quota_jobs_month": t["quota_jobs_month"],
            "onboarding": onboarding(t, bool(keys)), "keys": keys,
            "invited_by": (db.one("SELECT email FROM users WHERE id=?", (t["invited_by"],)) or {}).get("email") if t["invited_by"] else None,
            "projects": [project_summary(p) for p in db.q("SELECT * FROM projects WHERE user_id=? AND is_sample=0 ORDER BY updated DESC", (uid,))],
            "jobs": db.q("SELECT j.id,j.kind,j.status,j.engine,j.billing,j.created,j.error,p.name FROM jobs j LEFT JOIN projects p ON p.id=j.project_id "
                         "WHERE j.user_id=? ORDER BY j.id DESC LIMIT 15", (uid,)),
            "usage": db.one("SELECT COALESCE(SUM(input_tokens),0) i, COALESCE(SUM(output_tokens),0) o, COUNT(*) n FROM usage WHERE user_id=? AND created>=?",
                            (uid, db.now()[:7] + "-01")),
            "activity": db.q("SELECT action, target, created FROM audit WHERE user_id=? ORDER BY id DESC LIMIT 20", (uid,))}


@app.get("/api/admin/invites")
def list_invites(a=Depends(need_admin)):
    return db.q("SELECT i.*, u.email used_email, c.email created_email FROM invites i LEFT JOIN users u ON u.id=i.used_by "
                "LEFT JOIN users c ON c.id=i.created_by ORDER BY i.id DESC LIMIT 100")


@app.post("/api/admin/invites")
async def create_invite(request: Request, a=Depends(need_admin)):
    b = await body(request)
    email = str(b.get("email") or "").strip().lower() or None
    if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(400, "Email không hợp lệ")
    if email and db.one("SELECT id FROM users WHERE email=?", (email,)):
        raise HTTPException(409, "Email này đã có tài khoản")
    role = b.get("role") if b.get("role") in ("user", "admin") and (a["role"] == "owner" or b.get("role") == "user") else "user"
    days = to_int(b.get("days") or 7, "Số ngày hết hạn", 1, 90, allow_none=False)
    num = lambda k: to_int(b.get(k), k)  # noqa: E731
    iid = db.insert("invites", token=secrets.token_urlsafe(18), email=email, role=role, quota_projects=num("quota_projects"),
                    quota_jobs_month=num("quota_jobs_month"), note=str(b.get("note") or "")[:200], created_by=a["id"], created=db.now(),
                    expires=(dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=days)).replace(microsecond=0).isoformat())
    db.audit(a["id"], "invite_create", email or "(link mở)", {"role": role, "days": days})
    return db.one("SELECT * FROM invites WHERE id=?", (iid,))


@app.delete("/api/admin/invites/{iid}")
def revoke_invite(iid: int, a=Depends(need_admin)):
    db.update("invites", iid, revoked=1)
    db.audit(a["id"], "invite_revoke", iid)
    return {"ok": True}


@app.post("/api/admin/users")
async def admin_create_user(request: Request, a=Depends(need_admin)):
    b = await body(request)
    email = str(b.get("email", "")).strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or len(str(b.get("password", ""))) < 8:
        raise HTTPException(400, "Email hoặc mật khẩu (≥ 8 ký tự) không hợp lệ")
    if db.one("SELECT id FROM users WHERE email=?", (email,)):
        raise HTTPException(409, "Email đã tồn tại")
    role = b.get("role") if b.get("role") in ("user", "admin") and (a["role"] == "owner" or b.get("role") == "user") else "user"
    uid = db.insert("users", email=email, name=b.get("name") or email.split("@")[0], pw_hash=hash_pw(b["password"]),
                    role=role, status="active", created=db.now())
    db.audit(a["id"], "user_create", email, {"role": role})
    return public_user(db.one("SELECT * FROM users WHERE id=?", (uid,)))


@app.patch("/api/admin/users/{uid}")
async def admin_edit_user(uid: int, request: Request, a=Depends(need_admin)):
    t, b = db.one("SELECT * FROM users WHERE id=?", (uid,)), await body(request)
    if not t:
        raise HTTPException(404)
    if t["role"] == "owner" and a["role"] != "owner":
        raise HTTPException(403, "Không sửa được owner")
    kw = {}
    if "role" in b:
        if a["role"] != "owner" or b["role"] not in ("user", "admin", "owner") or t["id"] == a["id"]:
            raise HTTPException(403, "Chỉ owner đổi vai trò người khác")
        kw["role"] = b["role"]
    if b.get("status") in ("active", "disabled"):
        if t["id"] == a["id"]:
            raise HTTPException(400, "Không tự khoá chính mình")
        kw["status"] = b["status"]
        kw["session_ver"] = t["session_ver"] + 1
    for k in ("quota_projects", "quota_jobs_month"):
        if k in b:
            kw[k] = to_int(b[k], "Hạn mức", 0, 10000)
    if b.get("password"):
        if t["role"] != "user" and a["role"] != "owner":
            raise HTTPException(403, "Chỉ owner đặt lại mật khẩu cho admin")
        if len(b["password"]) < 8:
            raise HTTPException(400, "Mật khẩu tối thiểu 8 ký tự")
        kw.update(pw_hash=hash_pw(b["password"]), session_ver=t["session_ver"] + 1)
    db.update("users", uid, **kw)
    db.audit(a["id"], "user_update", t["email"], {k: v for k, v in kw.items() if k not in ("pw_hash",)})
    return {"ok": True}


@app.get("/api/admin/projects")
def admin_projects(a=Depends(need_admin)):
    rows = db.q("SELECT p.*, u.email FROM projects p JOIN users u ON u.id=p.user_id ORDER BY p.updated DESC")
    return [{**project_summary(p), "email": p["email"]} for p in rows]


@app.get("/api/admin/jobs")
def admin_jobs(status: str = "", a=Depends(need_admin)):
    sql = ("SELECT j.id,j.kind,j.status,j.engine,j.billing,j.model,j.attempt,j.created,j.started,j.finished,j.error,j.usage,"
           "p.slug,p.name,u.email,ap.name profile FROM jobs j LEFT JOIN projects p ON p.id=j.project_id LEFT JOIN users u ON u.id=j.user_id "
           "LEFT JOIN agent_profiles ap ON ap.id=j.profile_id")
    return db.q(sql + (" WHERE j.status=?" if status else "") + " ORDER BY j.id DESC LIMIT 200", (status,) if status else ())


@app.post("/api/admin/jobs/{jid}/retry")
def admin_retry(jid: int, a=Depends(need_admin)):
    j = db.one("SELECT * FROM jobs WHERE id=?", (jid,))
    if not j or j["status"] in ("queued", "starting", "running", "waiting") or j["kind"] != "plan":
        raise HTTPException(400, "Job không thể chạy lại")
    if not db.one("SELECT id FROM projects WHERE id=?", (j["project_id"],)):
        raise HTTPException(410, "Dự án của job này đã bị xoá — không chạy lại được.")
    owner_u = db.one("SELECT status FROM users WHERE id=?", (j["user_id"],))
    if not owner_u or owner_u["status"] != "active":
        raise HTTPException(409, "Người dùng của job đang bị khoá — mở khoá trước khi chạy lại.")
    if db.one("SELECT id FROM jobs WHERE project_id=? AND status IN ('queued','starting','running','waiting')", (j["project_id"],)):
        raise HTTPException(409, "Dự án đang có job khác chạy.")
    prof = agents.active_profile() if j["billing"] == "owner" else None
    nid = db.insert("jobs", kind=j["kind"], project_id=j["project_id"], user_id=j["user_id"], engine=prof["engine"] if prof else j["engine"],
                    billing=j["billing"], profile_id=prof["id"] if prof else j["profile_id"], api_key_id=j["api_key_id"],
                    model=j["model"], status="queued", created=db.now(), by_admin=a["id"])
    db.audit(a["id"], "job_retry", jid, {"new": nid})
    return {"job_id": nid}


@app.get("/api/admin/usage")
def admin_usage(a=Depends(need_admin)):
    month = db.now()[:7] + "-01"
    return {"by_user": db.q("SELECT u.email, g.source, SUM(g.input_tokens) i, SUM(g.output_tokens) o, COUNT(*) n FROM usage g "
                            "JOIN users u ON u.id=g.user_id WHERE g.created>=? GROUP BY u.email, g.source ORDER BY i+o DESC", (month,)),
            "by_profile": db.q("SELECT ap.name, ap.engine, SUM(g.input_tokens) i, SUM(g.output_tokens) o, SUM(g.cost_usd) c, COUNT(*) n "
                               "FROM usage g JOIN agent_profiles ap ON ap.id=g.profile_id WHERE g.created>=? GROUP BY ap.id", (month,)),
            "by_provider": db.q("SELECT provider, model, SUM(input_tokens) i, SUM(output_tokens) o, COUNT(*) n FROM usage WHERE created>=? "
                                "GROUP BY provider, model ORDER BY i+o DESC", (month,))}


@app.get("/api/admin/audit")
def admin_audit(a=Depends(need_admin)):
    return db.q("SELECT a.*, u.email FROM audit a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.id DESC LIMIT 300")


# --- core agent profiles (owner)
def profile_row(p):
    tok, n = agents.tokens_this_month(p["id"])
    return {**{k: v for k, v in p.items() if k != "key_enc"}, "models": json.loads(p["models"] or "[]"), "tokens_month": tok,
            "jobs_month": n, "installed": bool(agents.binary(p["engine"])) if p["engine"] != "demo" else True,
            "terminal": p["id"] in agents.TERMINALS and agents.TERMINALS[p["id"]].alive}


@app.get("/api/admin/agents")
def list_agents(o=Depends(need_owner)):
    st = sandbox.status()
    issues = [x for x in (agents.cli_problem(e) for e in ("agy", "claude")) if x]
    if issues:
        st = {**st, "enabled": False, "hint": " ".join(issues)}
    return {"sandbox": st, "profiles": [profile_row(p) for p in db.q("SELECT * FROM agent_profiles ORDER BY is_active DESC, priority, id")],
            "engines": {k: {"label": v["label"], "install": v["install"], "installed": bool(agents.binary(k)) if k != "demo" else True,
                            "key_label": v.get("key_label"), "actions": list(v["terminal"])} for k, v in agents.ENGINES.items()}}


def get_profile(pid):
    p = db.one("SELECT * FROM agent_profiles WHERE id=?", (pid,))
    if not p:
        raise HTTPException(404)
    return p


@app.post("/api/admin/agents")
async def add_agent(request: Request, o=Depends(need_owner)):
    b = await body(request)
    if b.get("engine") not in agents.ENGINES or not str(b.get("name", "")).strip():
        raise HTTPException(400, "Cần tên và engine hợp lệ")
    mode = "api_key" if b.get("auth_mode") == "api_key" else "account"
    key = str(b.get("key", "")).strip()
    first = not db.one("SELECT id FROM agent_profiles")
    pid = db.insert("agent_profiles", name=b["name"].strip(), engine=b["engine"], auth_mode=mode, key_enc=enc(key) if key else None,
                    key_hint=hint(key) if key else None, model=b.get("model") or None, enabled=1, is_active=int(first),
                    priority=to_int(b.get("priority") or 100, "Ưu tiên", 0, 10000), account_label=b.get("account_label"), status="new", created=db.now())
    db.update("agent_profiles", pid, home_dir=str(agents.AGENTS_HOME / str(pid)))
    db.audit(o["id"], "agent_add", b["name"], {"engine": b["engine"], "mode": mode})
    return profile_row(get_profile(pid))


@app.patch("/api/admin/agents/{pid}")
async def edit_agent(pid: int, request: Request, o=Depends(need_owner)):
    p, b = get_profile(pid), await body(request)
    kw = {k: str(b[k]).strip() or None for k in ("name", "model", "account_label") if k in b}
    for k in ("priority", "budget_tokens_month"):
        if k in b:
            kw[k] = to_int(b[k], k, 0, 10**12)
    if "enabled" in b:
        kw["enabled"] = int(bool(b["enabled"]))
        if not kw["enabled"] and p["is_active"]:                           # tắt tài khoản đang dùng → chuyển "đang dùng" sang tài khoản kế
            kw["is_active"] = 0
            nxt = agents.active_profile(exclude=(pid,))
            if nxt:
                db.update("agent_profiles", nxt["id"], is_active=1)
    if b.get("auth_mode") in ("account", "api_key"):
        kw["auth_mode"] = b["auth_mode"]
    if b.get("key"):
        kw.update(key_enc=enc(b["key"].strip()), key_hint=hint(b["key"].strip()))
    if b.get("reset_status"):
        kw["status"] = "ready"
    db.update("agent_profiles", pid, **kw)
    db.audit(o["id"], "agent_update", p["name"], {k: v for k, v in kw.items() if k != "key_enc"})
    return profile_row(get_profile(pid))


@app.post("/api/admin/agents/{pid}/activate")
def activate_agent(pid: int, o=Depends(need_owner)):
    p = get_profile(pid)
    db.x("UPDATE agent_profiles SET is_active=0")
    db.update("agent_profiles", pid, is_active=1, enabled=1)
    db.audit(o["id"], "agent_activate", p["name"])
    return {"ok": True}


@app.delete("/api/admin/agents/{pid}")
def delete_agent(pid: int, o=Depends(need_owner)):
    p = get_profile(pid)
    agents.terminal_finish(pid)
    db.x("DELETE FROM agent_profiles WHERE id=?", (pid,))
    shutil.rmtree(agents.home(p), ignore_errors=True)      # xoá luôn phiên đăng nhập lưu trong HOME của profile
    db.audit(o["id"], "agent_delete", p["name"])
    return {"ok": True}


@app.post("/api/admin/agents/{pid}/check")
def check_agent(pid: int, o=Depends(need_owner)):
    code, out = agents.check(get_profile(pid))
    return {"ok": code == 0, "output": out}


@app.post("/api/admin/agents/{pid}/models")
def agent_models(pid: int, o=Depends(need_owner)):
    models, out = agents.list_models(get_profile(pid))
    return {"models": models, "output": out}


@app.post("/api/admin/agents/install")
async def install_cli(request: Request, o=Depends(need_owner)):
    b = await body(request)
    if b.get("engine") not in ("agy", "claude"):
        raise HTTPException(400)
    jid = db.insert("jobs", kind="install", engine=b["engine"], user_id=o["id"], status="queued", created=db.now())
    db.audit(o["id"], "cli_install", b["engine"])
    return {"job_id": jid}


@app.post("/api/admin/agents/{pid}/terminal")
async def term_start(pid: int, request: Request, o=Depends(need_owner)):
    b = await body(request)
    try:
        agents.terminal_start(get_profile(pid), b.get("action", "login"))
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    db.audit(o["id"], "agent_terminal", pid, {"action": b.get("action")})
    return {"ok": True}


@app.get("/api/admin/agents/{pid}/terminal")
def term_view(pid: int, o=Depends(need_owner)):
    t = agents.TERMINALS.get(pid)
    return t.view() if t else {"output": "", "urls": [], "alive": False, "action": None}


@app.post("/api/admin/agents/{pid}/terminal/input")
async def term_input(pid: int, request: Request, o=Depends(need_owner)):
    t, b = agents.TERMINALS.get(pid), await body(request)
    if not t:
        raise HTTPException(400, "Terminal chưa mở")
    t.send(str(b.get("text", "")) + ("\r" if b.get("enter", True) else ""))
    return {"ok": True}


@app.post("/api/admin/agents/{pid}/terminal/stop")
def term_stop(pid: int, o=Depends(need_owner)):
    agents.terminal_finish(pid)
    return {"ok": True}


# --- settings (owner)
EDITABLE = {"site_name", "allow_signup", "plan_billing", "default_quota_projects", "default_quota_jobs_month", "job_timeout_min",
            "max_concurrent_jobs", "auto_failover", "allow_demo_engine", "google_client_id", "public_base_url"}


NUMERIC = {"default_quota_projects": (0, 10000), "default_quota_jobs_month": (0, 10000), "job_timeout_min": (5, 1440), "max_concurrent_jobs": (1, 16)}
SETTING_LABEL = {"default_quota_projects": "Số dự án tối đa", "default_quota_jobs_month": "Số lần chạy / tháng",
                 "job_timeout_min": "Thời gian tối đa mỗi job", "max_concurrent_jobs": "Số job song song"}


@app.get("/api/admin/settings")
def get_settings(o=Depends(need_owner)):
    s = {r["key"]: r["value"] for r in db.q("SELECT * FROM settings") if r["key"] in EDITABLE}
    return {**s, "google_client_secret_set": bool(db.setting("google_client_secret_enc"))}


@app.put("/api/admin/settings")
async def put_settings(request: Request, o=Depends(need_owner)):
    b = await body(request)
    for k, (lo, hi) in NUMERIC.items():
        if k in b:
            b[k] = to_int(b[k], SETTING_LABEL.get(k, k), lo, hi, allow_none=False)
    for k in ("allow_signup", "auto_failover", "allow_demo_engine"):
        if k in b and str(b[k]) not in ("0", "1"):
            raise HTTPException(400, f"{k}: 0 hoặc 1")
    if "plan_billing" in b and b["plan_billing"] not in ("owner", "user_key", "either"):
        raise HTTPException(400, "plan_billing không hợp lệ")
    if "site_name" in b and not str(b["site_name"]).strip():
        raise HTTPException(400, "Tên hệ thống không được trống")
    if str(b.get("public_base_url") or "").strip():                      # dùng trong redirect OAuth và link chia sẻ
        u = urllib.parse.urlsplit(str(b["public_base_url"]).strip())
        if u.scheme not in ("http", "https") or not u.netloc or u.query or u.fragment:
            raise HTTPException(400, "Địa chỉ công khai phải dạng https://ten-mien.com (không kèm ?… hay #…)")
        b["public_base_url"] = str(b["public_base_url"]).strip().rstrip("/")
    for k, v in b.items():
        if k in EDITABLE:
            db.set_setting(k, str(v).strip())
    if b.get("google_client_secret"):
        db.set_setting("google_client_secret_enc", enc(b["google_client_secret"]))
    if b.get("clear_google_client_secret"):
        db.set_setting("google_client_secret_enc", "")
    db.audit(o["id"], "settings_update", "", {k: v for k, v in b.items() if k in EDITABLE})
    return get_settings(o)


SAMPLE_SLUG = "ai-robot-pet-mau"


def ensure_sample(owner_id):
    """Dự án mẫu dùng chung: mọi người dùng mới xem được ngay một bộ hồ sơ hoàn chỉnh (chỉ đọc)."""
    if db.one("SELECT id FROM projects WHERE slug=?", (SAMPLE_SLUG,)):
        return False
    src, dst = ROOT / "projects" / "ai-robot-pet", WORKSPACE / SAMPLE_SLUG
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("build"), dirs_exist_ok=True)
    pid = db.insert("projects", slug=SAMPLE_SLUG, user_id=owner_id, name="Hệ sinh thái AI Robot Pet Việt (mẫu)",
                    idea=(src / "idea.md").read_text(), status="running", is_sample=1, created=db.now(), updated=db.now())
    interview.start_interview(db.one("SELECT * FROM projects WHERE id=?", (pid,)))
    env = worker.base_env()
    for cmd in (["gen.py", "build", SAMPLE_SLUG], ["tools/export.py", SAMPLE_SLUG, "--media-base", f"/api/projects/{SAMPLE_SLUG}/media"]):
        subprocess.run([sys.executable, str(ROOT / cmd[0]), *cmd[1:]], env=env, cwd=ROOT, capture_output=True, timeout=600)
    history.ensure(SAMPLE_SLUG)
    db.update("projects", pid, status="done", updated=db.now())
    return True


@app.post("/api/admin/seed-sample")
def seed_sample(o=Depends(need_owner)):
    if not ensure_sample(o["id"]):
        raise HTTPException(409, "Đã nạp mẫu rồi")
    db.audit(o["id"], "seed_sample", SAMPLE_SLUG)
    return {"slug": SAMPLE_SLUG}
