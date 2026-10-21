"""Tài khoản & dự án của người dùng: hồ sơ, tuỳ chọn, đăng xuất thiết bị khác, mức dùng, xuất dữ liệu, xoá tài khoản,
nhân bản và lưu trữ dự án."""
import io
import json
import os
import tempfile
import time
import zipfile

os.environ.setdefault("GP_DATA", tempfile.mkdtemp(prefix="gp-test-"))

from fastapi.testclient import TestClient  # noqa: E402

from saas.server import db, history, main  # noqa: E402
from saas.server.config import WORKSPACE  # noqa: E402

X = {"X-GP": "1"}


def login(c, email, pw="password1"):
    if c.post("/api/auth/signup", json={"email": email, "password": pw}, headers=X).status_code != 200:
        assert c.post("/api/auth/login", json={"email": email, "password": pw}, headers=X).status_code == 200


def wait(c, jid):
    for _ in range(200):
        j = c.get(f"/api/jobs/{jid}").json()
        if j["status"] not in ("queued", "starting", "running"):
            return j
        time.sleep(0.2)


def test_profile_prefs_and_sessions():
    db.set_setting("allow_demo_engine", "1")
    with TestClient(main.app, headers=X) as a, TestClient(main.app, headers=X) as other:
        login(a, "acct@x.io")
        login(other, "acct@x.io")
        me = a.patch("/api/me", json={"name": "  Ryan  ", "prefs": {"theme": "dark", "country": "Singapore"}}).json()
        assert me["name"] == "Ryan" and me["prefs"] == {"theme": "dark", "country": "Singapore"}
        assert a.patch("/api/me", json={"prefs": {"theme": "neon"}}).status_code == 400
        p = a.post("/api/projects", json={"name": "Mặc định thị trường", "idea": "Dự án để thử thị trường mặc định của người dùng."}).json()
        assert p["country"] == "Singapore"
        assert a.post("/api/me/logout-others").status_code == 200
        assert other.get("/api/me").status_code == 401 and a.get("/api/me").status_code == 200
        u = a.get("/api/me/usage").json()
        assert "quota" in u and isinstance(u["months"], list)


def test_duplicate_archive_export_and_delete_account():
    with TestClient(main.app, headers=X) as a, TestClient(main.app, headers=X) as adm:
        login(a, "dup@x.io")
        login(adm, "dup-admin@x.io")
        db.x("UPDATE users SET role='admin' WHERE email='dup-admin@x.io'")
        p = a.post("/api/projects", json={"name": "Gốc", "idea": "Dự án gốc để nhân bản, lưu trữ và xuất dữ liệu."}).json()
        slug = p["slug"]
        a.post(f"/api/projects/{slug}/decisions", json={"title": "Chốt mảng đồ uống trước", "status": "locked"})
        assert wait(a, a.post(f"/api/projects/{slug}/run", json={"billing": "demo", "force": True}).json()["job_id"])["status"] == "done"
        assert adm.post(f"/api/projects/{slug}/duplicate").status_code == 403          # admin không chép dữ liệu riêng về
        d = a.post(f"/api/projects/{slug}/duplicate").json()
        assert d["name"] == "Gốc (bản sao)" and d["locked"] == 1
        assert (WORKSPACE / d["slug"] / "assumptions.yaml").exists() and not (WORKSPACE / d["slug"] / ".git").exists()
        assert history.log(d["slug"]) and "Nhân bản" in history.log(d["slug"])[0]["message"]
        assert (WORKSPACE / d["slug"]).stat().st_mode & 0o777 == 0o700 or os.geteuid() != 0
        a.patch(f"/api/projects/{slug}", json={"archived": True})
        rows = a.get("/api/projects").json()
        assert rows[-1]["slug"] == slug and rows[-1]["archived"] == 1             # lưu trữ xuống cuối
        sample = a.get("/api/samples").json()
        if sample:
            assert a.post(f"/api/projects/{sample[0]['slug']}/duplicate").status_code == 200

        a.post("/api/keys", json={"provider": "anthropic", "key": "sk-ant-secret-value-123456"})
        z = zipfile.ZipFile(io.BytesIO(a.get("/api/me/export").content))
        names = z.namelist()
        assert "account.json" in names and f"projects/{slug}/project.json" in names and f"projects/{slug}/dossier.zip" in names
        blob = b"".join(z.read(n) for n in names if not n.endswith(".zip"))
        assert b"secret-value" not in blob and b"Ch\\u1ed1t" not in blob
        assert "Chốt mảng đồ uống trước" in json.loads(z.read(f"projects/{slug}/project.json"))["decisions"][0]["title"]

        assert a.post("/api/me/delete", json={"confirm": "khac@x.io", "password": "password1"}).status_code == 400
        assert a.post("/api/me/delete", json={"confirm": "dup@x.io", "password": "sai-mat-khau"}).status_code == 400
        assert a.post("/api/me/delete", json={"confirm": "dup@x.io", "password": "password1"}).status_code == 200
        assert not db.one("SELECT id FROM users WHERE email='dup@x.io'")
        assert not (WORKSPACE / slug).exists() and not (WORKSPACE / d["slug"]).exists() and not history.git_dir(slug).exists()
        assert a.get("/api/me").status_code == 401


def test_owner_cannot_delete_self():
    with TestClient(main.app, headers=X) as o:
        login(o, "own-del@x.io")
        db.x("UPDATE users SET role='owner' WHERE email='own-del@x.io'")
        r = o.post("/api/me/delete", json={"confirm": "own-del@x.io", "password": "password1"})
        assert r.status_code == 400 and "trao quyền" in r.json()["detail"]
