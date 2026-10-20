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
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse

from . import agents, db, interview, llm, worker
from .config import COOKIE_SECURE, ROOT, SAAS, WORKSPACE
from .security import check_pw, dec, enc, hash_pw, hint, sign, unsign

app = FastAPI(title="Gen Planner", docs_url=None, redoc_url=None)
STATIC = SAAS / "static"
COOKIE = "gp_session"
_attempts: dict[str, list[float]] = defaultdict(list)


@app.on_event("startup")
def _start():
    worker.start()


@app.middleware("http")
async def csrf(request: Request, call_next):
    # Mọi lệnh ghi phải mang header X-GP (form chéo site không đặt được header tuỳ ý)
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.url.path.startswith("/api/") \
            and request.headers.get("x-gp") != "1":
        return JSONResponse({"detail": "Thiếu header X-GP"}, status_code=403)
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    return resp


# ------------------------------------------------------------------ auth helpers
def current_user(request: Request):
    s = unsign(request.cookies.get(COOKIE, ""))
    if not s:
        return None
    u = db.one("SELECT * FROM users WHERE id=?", (s.get("uid"),))
    if not u or u["status"] != "active" or u["session_ver"] != s.get("v"):
        return None
    return u


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


def throttle(request: Request):
    ip = request.client.host if request.client else "?"
    now = time.time()
    _attempts[ip] = [t for t in _attempts[ip] if now - t < 300]
    if len(_attempts[ip]) >= 10:
        raise HTTPException(429, "Thử quá nhiều lần, đợi 5 phút.")
    _attempts[ip].append(now)


def create_user(email, name, pw=None, google_sub=None):
    first = db.one("SELECT COUNT(*) n FROM users")["n"] == 0
    if not first and db.setting("allow_signup") != "1":
        raise HTTPException(403, "Hệ thống đang tắt đăng ký mới. Liên hệ admin.")
    uid = db.insert("users", email=email, name=name or email.split("@")[0], pw_hash=hash_pw(pw) if pw else None,
                    google_sub=google_sub, role="owner" if first else "user", status="active", created=db.now())
    db.audit(uid, "signup", email, {"role": "owner" if first else "user"})
    return db.one("SELECT * FROM users WHERE id=?", (uid,))


async def body(request: Request) -> dict:
    try:
        return await request.json()
    except (json.JSONDecodeError, ValueError):
        return {}


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
    if not re.fullmatch(r"[\w.-]+", f) or not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


# ------------------------------------------------------------------ auth API
@app.get("/api/public")
def public():
    return {"site_name": db.setting("site_name"), "allow_signup": db.setting("allow_signup") == "1",
            "google": bool(db.setting("google_client_id")), "has_owner": db.one("SELECT COUNT(*) n FROM users")["n"] > 0}


@app.post("/api/auth/signup")
async def signup(request: Request):
    throttle(request)
    b = await body(request)
    email, pw = str(b.get("email", "")).strip().lower(), str(b.get("password", ""))
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or len(pw) < 8:
        raise HTTPException(400, "Email không hợp lệ hoặc mật khẩu dưới 8 ký tự.")
    if db.one("SELECT id FROM users WHERE email=?", (email,)):
        raise HTTPException(409, "Email đã có tài khoản.")
    return login_response(create_user(email, b.get("name"), pw))


@app.post("/api/auth/login")
async def login(request: Request):
    throttle(request)
    b = await body(request)
    u = db.one("SELECT * FROM users WHERE email=?", (str(b.get("email", "")).strip().lower(),))
    if not u or not check_pw(str(b.get("password", "")), u["pw_hash"]):
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
            "plan_billing": db.setting("plan_billing"), "quota": quota(u), "demo_allowed": db.setting("allow_demo_engine") == "1"}


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
    used_jobs = db.one("SELECT COUNT(*) n FROM jobs WHERE user_id=? AND billing='owner' AND engine!='demo' AND created>=? "
                       "AND status NOT IN ('cancelled')", (u["id"], month))["n"]
    projects = db.one("SELECT COUNT(*) n FROM projects WHERE user_id=?", (u["id"],))["n"]
    lim_p = u["quota_projects"] if u["quota_projects"] is not None else int(db.setting("default_quota_projects", "5"))
    lim_j = u["quota_jobs_month"] if u["quota_jobs_month"] is not None else int(db.setting("default_quota_jobs_month", "3"))
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


@app.post("/api/keys/{kid}/test")
def test_key(kid: int, u=Depends(need_user)):
    k = my_key(u, kid)
    try:
        text, usage = llm.chat(k["provider"], dec(k["key_enc"]), k["model"], "Trả lời đúng một từ: OK",
                               [{"role": "user", "content": "ping"}], max_tokens=10)
        ok, msg = True, text.strip()[:60] or "OK"
    except llm.LLMError as e:
        ok, msg = False, str(e)
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
    if p["user_id"] != u["id"] and (write or u["role"] not in ("owner", "admin")):
        raise HTTPException(403, "Không phải dự án của bạn")
    return p


def project_summary(p):
    j = db.one("SELECT id,status,engine,billing,created,finished,error FROM jobs WHERE project_id=? ORDER BY id DESC LIMIT 1", (p["id"],))
    st = interview.state(p["id"])
    return {**{k: p[k] for k in ("id", "slug", "name", "country", "status", "created", "updated")},
            "progress": interview.progress(st["answers"]), "last_job": j,
            "exported": (WORKSPACE / p["slug"] / "build" / "export" / "project.json").exists(),
            "locked": db.one("SELECT COUNT(*) n FROM decisions WHERE project_id=? AND status='locked'", (p["id"],))["n"]}


@app.get("/api/projects")
def my_projects(u=Depends(need_user)):
    return [project_summary(p) for p in db.q("SELECT * FROM projects WHERE user_id=? ORDER BY updated DESC", (u["id"],))]


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
            "jobs": db.q("SELECT id,status,engine,billing,model,created,started,finished,error,usage FROM jobs WHERE project_id=? "
                         "ORDER BY id DESC LIMIT 10", (p["id"],)),
            "mine": p["user_id"] == u["id"]}


@app.patch("/api/projects/{slug}")
async def edit_project(slug: str, request: Request, u=Depends(need_user)):
    p, b = get_project(slug, u, True), await body(request)
    kw = {k: str(b[k]).strip() for k in ("name", "idea", "country") if b.get(k)}
    db.update("projects", p["id"], **kw, updated=db.now())
    return project_summary(db.one("SELECT * FROM projects WHERE id=?", (p["id"],)))


@app.delete("/api/projects/{slug}")
def delete_project(slug: str, u=Depends(need_user)):
    p = get_project(slug, u, True)
    for t in ("messages", "decisions", "interview"):
        db.x(f"DELETE FROM {t} WHERE project_id=?", (p["id"],))
    db.x("DELETE FROM projects WHERE id=?", (p["id"],))
    shutil.rmtree(WORKSPACE / p["slug"], ignore_errors=True)
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
    if db.one("SELECT id FROM jobs WHERE project_id=? AND status IN ('queued','starting','running')", (p["id"],)):
        raise HTTPException(409, "Dự án đang có job chạy.")
    missing = interview.progress(interview.state(p["id"])["answers"])["required_missing"]
    if missing and not b.get("force"):
        raise HTTPException(400, "Còn câu phỏng vấn bắt buộc chưa trả lời: " + ", ".join(missing))
    interview.build_brief(p)
    billing, mode = b.get("billing", "owner"), db.setting("plan_billing")
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


def get_job(jid, u):
    j = db.one("SELECT * FROM jobs WHERE id=?", (jid,))
    if not j or (j["user_id"] != u["id"] and u["role"] not in ("owner", "admin")):
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
    if j["status"] in ("queued", "starting", "running"):
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
    f = WORKSPACE / slug / "media" / name
    if not re.fullmatch(r"[\w.-]+", name) or not f.exists():
        raise HTTPException(404)
    return FileResponse(f)


FILES = {"business-plan.docx", "deck.pptx", "financials.xlsx", "business-plan.md"}


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
            "days": days, "active_agent": agents.active_profile(),
            "recent_jobs": db.q("SELECT j.id,j.status,j.engine,j.billing,j.created,p.slug,p.name,u.email FROM jobs j LEFT JOIN projects p ON p.id=j.project_id "
                                "LEFT JOIN users u ON u.id=j.user_id ORDER BY j.id DESC LIMIT 8")}


@app.get("/api/admin/users")
def admin_users(a=Depends(need_admin)):
    out = []
    for u in db.q("SELECT * FROM users ORDER BY id"):
        tok = db.one("SELECT COALESCE(SUM(input_tokens+output_tokens),0) n FROM usage WHERE user_id=? AND created>=?", (u["id"], db.now()[:7] + "-01"))["n"]
        out.append({**public_user(u), "quota": quota(u), "quota_projects": u["quota_projects"], "quota_jobs_month": u["quota_jobs_month"],
                    "keys": db.one("SELECT COUNT(*) n FROM api_keys WHERE user_id=?", (u["id"],))["n"], "tokens_month": tok,
                    "google": bool(u["google_sub"])})
    return out


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
            kw[k] = None if b[k] in (None, "") else int(b[k])
    if b.get("password"):
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
    if not j or j["status"] in ("queued", "starting", "running"):
        raise HTTPException(400, "Job không thể chạy lại")
    prof = agents.active_profile() if j["billing"] == "owner" else None
    nid = db.insert("jobs", kind=j["kind"], project_id=j["project_id"], user_id=j["user_id"], engine=prof["engine"] if prof else j["engine"],
                    billing=j["billing"], profile_id=prof["id"] if prof else j["profile_id"], api_key_id=j["api_key_id"],
                    model=j["model"], status="queued", created=db.now())
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
    return {"profiles": [profile_row(p) for p in db.q("SELECT * FROM agent_profiles ORDER BY is_active DESC, priority, id")],
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
                    priority=int(b.get("priority") or 100), account_label=b.get("account_label"), status="new", created=db.now())
    db.update("agent_profiles", pid, home_dir=str(agents.AGENTS_HOME / str(pid)))
    db.audit(o["id"], "agent_add", b["name"], {"engine": b["engine"], "mode": mode})
    return profile_row(get_profile(pid))


@app.patch("/api/admin/agents/{pid}")
async def edit_agent(pid: int, request: Request, o=Depends(need_owner)):
    p, b = get_profile(pid), await body(request)
    kw = {k: b[k] for k in ("name", "model", "account_label", "priority", "budget_tokens_month") if k in b}
    if "enabled" in b:
        kw["enabled"] = int(bool(b["enabled"]))
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


@app.get("/api/admin/settings")
def get_settings(o=Depends(need_owner)):
    s = {r["key"]: r["value"] for r in db.q("SELECT * FROM settings") if r["key"] in EDITABLE}
    return {**s, "google_client_secret_set": bool(db.setting("google_client_secret_enc"))}


@app.put("/api/admin/settings")
async def put_settings(request: Request, o=Depends(need_owner)):
    b = await body(request)
    for k, v in b.items():
        if k in EDITABLE:
            db.set_setting(k, v)
    if b.get("google_client_secret"):
        db.set_setting("google_client_secret_enc", enc(b["google_client_secret"]))
    db.audit(o["id"], "settings_update", "", {k: v for k, v in b.items() if k in EDITABLE})
    return get_settings(o)


@app.post("/api/admin/seed-sample")
def seed_sample(o=Depends(need_owner)):
    """Nạp dự án mẫu projects/ai-robot-pet vào workspace của owner để xem trình xem với dữ liệu thật."""
    slug = "ai-robot-pet-mau"
    if db.one("SELECT id FROM projects WHERE slug=?", (slug,)):
        raise HTTPException(409, "Đã nạp mẫu rồi")
    src, dst = ROOT / "projects" / "ai-robot-pet", WORKSPACE / slug
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("build"), dirs_exist_ok=True)
    idea = (src / "idea.md").read_text()
    pid = db.insert("projects", slug=slug, user_id=o["id"], name="Hệ sinh thái AI Robot Pet Việt (mẫu)", idea=idea,
                    status="done", created=db.now(), updated=db.now())
    interview.start_interview(db.one("SELECT * FROM projects WHERE id=?", (pid,)))
    env = worker.base_env()
    for cmd in (["gen.py", "build", slug], ["tools/export.py", slug, "--media-base", f"/api/projects/{slug}/media"]):
        subprocess.run([sys.executable, str(ROOT / cmd[0]), *cmd[1:]], env=env, cwd=ROOT, capture_output=True, timeout=600)
    db.audit(o["id"], "seed_sample", slug)
    return {"slug": slug}
