"""Lỗi owner/admin & độ bền mà QA đã gặp: agent mồ côi sau khi máy chủ chết, chạy lại job của dự án đã xoá, admin chạy lại
bị trừ hạn mức người dùng, phễu sai, URL công khai độc, tắt tài khoản agent đang dùng."""
import os
import subprocess
import sys
import tempfile
import time

os.environ.setdefault("GP_DATA", tempfile.mkdtemp(prefix="gp-test-"))

from fastapi.testclient import TestClient  # noqa: E402

from saas.server import db, main, worker  # noqa: E402
from saas.server.config import WORKSPACE  # noqa: E402

X = {"X-GP": "1"}


def login(c, email, role=None):
    if c.post("/api/auth/signup", json={"email": email, "password": "password1"}, headers=X).status_code != 200:
        c.post("/api/auth/login", json={"email": email, "password": "password1"}, headers=X)
    if role:
        db.x("UPDATE users SET role=? WHERE email=?", (role, email))


def test_recover_kills_only_our_orphan_agents():
    ours = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True,
                            env={**os.environ, "GP_PROJECTS": str(WORKSPACE)})
    stranger = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True,
                                env={k: v for k, v in os.environ.items() if k != "GP_PROJECTS"})
    try:
        j1 = db.insert("jobs", kind="plan", status="running", engine="agy", billing="owner", pid=ours.pid, created=db.now())
        j2 = db.insert("jobs", kind="plan", status="running", engine="agy", billing="owner", pid=stranger.pid, created=db.now())
        worker.recover()
        time.sleep(0.5)
        assert ours.poll() is not None                                        # agent của mình: đã dừng
        assert stranger.poll() is None                                        # PID bị tái dùng bởi tiến trình khác: không đụng
        for j in (j1, j2):
            row = db.one("SELECT * FROM jobs WHERE id=?", (j,))
            assert row["status"] == "failed" and row["system_fault"] == 1 and row["pid"] is None
        assert "dừng agent còn sót" in db.one("SELECT log FROM jobs WHERE id=?", (j1,))["log"]
    finally:
        for p in (ours, stranger):
            p.kill()


def test_admin_retry_rules_and_quota():
    with TestClient(main.app, headers=X) as adm, TestClient(main.app, headers=X) as u:
        login(adm, "adm-retry@x.io", "owner")
        login(u, "user-retry@x.io")
        uid = db.one("SELECT id FROM users WHERE email='user-retry@x.io'")["id"]
        slug = u.post("/api/projects", json={"name": "Retry", "idea": "Dự án để thử chạy lại job từ trang quản trị."}).json()["slug"]
        pid = db.one("SELECT id FROM projects WHERE slug=?", (slug,))["id"]
        jid = db.insert("jobs", kind="plan", project_id=pid, user_id=uid, status="failed", engine="agy", billing="owner",
                        started=db.now(), created=db.now())
        assert u.get("/api/me").json()["quota"]["owner_jobs_month"] == 1
        sysj = db.insert("jobs", kind="plan", project_id=pid, user_id=uid, status="failed", engine="agy", billing="owner",
                         started=db.now(), created=db.now(), system_fault=1)
        assert u.get("/api/me").json()["quota"]["owner_jobs_month"] == 1      # lỗi phía hệ thống: không trừ
        r = adm.post(f"/api/admin/jobs/{jid}/retry")
        assert r.status_code == 200
        db.x("UPDATE jobs SET status='failed', started=? WHERE id=?", (db.now(), r.json()["job_id"]))
        assert u.get("/api/me").json()["quota"]["owner_jobs_month"] == 1      # admin chạy lại: không trừ
        db.x("UPDATE users SET status='disabled' WHERE id=?", (uid,))
        assert adm.post(f"/api/admin/jobs/{sysj}/retry").status_code == 409
        db.x("UPDATE users SET status='active' WHERE id=?", (uid,))
        db.x("DELETE FROM projects WHERE id=?", (pid,))
        r = adm.post(f"/api/admin/jobs/{sysj}/retry")
        assert r.status_code == 410 and "đã bị xoá" in r.json()["detail"]


def test_settings_validation_and_profile_disable():
    with TestClient(main.app, headers=X) as o:
        login(o, "owner-set@x.io", "owner")
        for bad in ("javascript:alert(1)", "https://x.io/?a=1", "ftp://x.io"):
            assert o.put("/api/admin/settings", json={"public_base_url": bad}).status_code == 400
        assert o.put("/api/admin/settings", json={"public_base_url": "https://plan.afi.io/"}).json()["public_base_url"] == "https://plan.afi.io"
        o.put("/api/admin/settings", json={"public_base_url": ""})
        a = o.post("/api/admin/agents", json={"engine": "demo", "name": "A"}).json()
        b = o.post("/api/admin/agents", json={"engine": "demo", "name": "B"}).json()
        o.post(f"/api/admin/agents/{a['id']}/activate")
        o.patch(f"/api/admin/agents/{a['id']}", json={"enabled": False})
        rows = {p["id"]: p for p in o.get("/api/admin/agents").json()["profiles"]}
        active = [p for p in rows.values() if p["is_active"]]
        assert not rows[a["id"]]["is_active"] and len(active) == 1 and active[0]["enabled"]   # tắt tài khoản đang dùng → chuyển sang tài khoản kế
        for p in (a, b):
            o.delete(f"/api/admin/agents/{p['id']}")
