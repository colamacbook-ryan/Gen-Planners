"""Quét quyền tự động trên MỌI route của API: người lạ, người dùng khác, user thường vào admin, admin vào trang owner."""
import os
import re
import tempfile
import time

os.environ.setdefault("GP_DATA", tempfile.mkdtemp(prefix="gp-test-"))

from fastapi.testclient import TestClient  # noqa: E402

from saas.server import db, main  # noqa: E402

H = {"X-GP": "1"}
PUBLIC = {"/api/public", "/api/auth/signup", "/api/auth/login", "/api/auth/logout", "/api/auth/google", "/api/auth/google/callback", "/api/auth/forgot", "/api/auth/reset"}
OWNER_ONLY = re.compile(r"^/api/admin/(agents|settings|seed-sample)")


def routes():
    for r in main.app.routes:
        if getattr(r, "path", "").startswith("/api/"):
            for m in r.methods - {"HEAD", "OPTIONS"}:
                yield m, r.path


def fill(path, ids):
    return re.sub(r"\{(\w+)\}", lambda m: str(ids.get(m.group(1), "1")), path)


def call(c, m, path):
    return c.request(m, path, json={} if m in ("POST", "PUT", "PATCH") else None)


def test_route_matrix():
    with TestClient(main.app, headers=H) as owner, TestClient(main.app, headers=H) as a, TestClient(main.app, headers=H) as b, \
            TestClient(main.app, headers=H) as admin, TestClient(main.app, headers=H) as anon:
        owner.post("/api/auth/login", json={"email": "owner@x.io", "password": "password1"}).status_code == 200 or \
            owner.post("/api/auth/signup", json={"email": "owner@x.io", "password": "password1"})
        owner.put("/api/admin/settings", json={"allow_signup": "1"})
        for c, e in ((a, "a@authz.io"), (b, "b@authz.io"), (admin, "adm@authz.io")):
            c.post("/api/auth/signup", json={"email": e, "password": "password1"}).status_code in (200, 409) or None
            c.post("/api/auth/login", json={"email": e, "password": "password1"})
        adm_id = next(u["id"] for u in owner.get("/api/admin/users").json() if u["email"] == "adm@authz.io")
        owner.patch(f"/api/admin/users/{adm_id}", json={"role": "admin"})
        admin.post("/api/auth/login", json={"email": "adm@authz.io", "password": "password1"})
        p = a.post("/api/projects", json={"name": "Dự án của A", "idea": "Ý tưởng bí mật của A, không ai khác được đọc."}).json()
        j = a.post(f"/api/projects/{p['slug']}/run", json={"billing": "demo", "force": True}).json()["job_id"]
        for _ in range(240):
            if a.get(f"/api/jobs/{j}").json()["status"] in ("done", "failed"):
                break
            time.sleep(0.5)
        d = a.post(f"/api/projects/{p['slug']}/decisions", json={"title": "Điểm của A"}).json()
        k = a.post("/api/keys", json={"provider": "anthropic", "key": "sk-ant-secret-1234567890"}).json()
        sh = a.post(f"/api/projects/{p['slug']}/shares", json={}).json()
        ids = {"slug": p["slug"], "did": d["id"], "kid": k["id"], "jid": j, "sid": sh["id"], "token": "khong-ton-tai",
               "uid": adm_id, "iid": 1, "pid": 1, "part": "project", "name": "business-plan.md", "key": "price_main", "f": "gp.js"}
        problems, checks = [], 0
        for m, path in sorted(set(routes())):
            url = fill(path, ids)
            if path in PUBLIC or path.startswith("/api/share/"):
                continue
            checks += 1
            r = call(anon, m, url)                                         # 1. người lạ: luôn 401
            if r.status_code != 401:
                problems.append(f"anon {m} {path} → {r.status_code}")
            if path.startswith("/api/admin/"):
                r = call(b, m, url)                                        # 2. user thường vào admin: 403
                if r.status_code != 403:
                    problems.append(f"user {m} {path} → {r.status_code}")
                if OWNER_ONLY.match(path):
                    r = call(admin, m, url)                                # 3. admin vào trang chỉ-owner: 403
                    if r.status_code != 403:
                        problems.append(f"admin {m} {path} → {r.status_code}")
            elif "{slug}" in path or any(x in path for x in ("{did}", "{kid}", "{jid}", "{sid}")):
                r = call(b, m, url)                                        # 4. người dùng khác đụng tài nguyên của A
                if r.status_code < 400:
                    problems.append(f"other-user {m} {path} → {r.status_code}")
        assert not problems, "\n".join(problems)
        assert checks >= 60, checks                                         # test thật sự quét đủ route
        # dữ liệu của A vẫn nguyên sau loạt tấn công của B
        assert a.get(f"/api/projects/{p['slug']}").json()["decisions"][0]["title"] == "Điểm của A"
        assert any(x["id"] == k["id"] for x in a.get("/api/keys").json())
        # API key không bao giờ trả nguyên văn
        assert "secret" not in a.get("/api/keys").text and "secret" not in owner.get(f"/api/admin/users/{a.get('/api/me').json()['id']}").text
        # thiếu header X-GP → mọi lệnh ghi bị chặn
        assert TestClient(main.app).post("/api/projects", json={}).status_code == 403
        # link chia sẻ chỉ mở đúng dự án của nó
        assert anon.get(f"/api/share/{sh['token']}/projects/khac/export/project").status_code == 404
        assert anon.get(f"/api/share/{sh['token']}/projects/{p['slug']}/media/..%2F..%2Fapp.db").status_code == 404
        assert db.one("SELECT COUNT(*) n FROM users")["n"] >= 4
