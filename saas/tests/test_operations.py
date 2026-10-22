"""Vận hành cho owner: chỉ số, xuất CSV, sao lưu, đăng ký theo tên miền, chế độ bảo trì, thông báo, chính sách lưu log."""
import csv
import io
import os
import sqlite3
import tempfile
import zipfile

os.environ.setdefault("GP_DATA", tempfile.mkdtemp(prefix="gp-test-"))

from fastapi.testclient import TestClient  # noqa: E402

from saas.server import db, main, worker  # noqa: E402

X = {"X-GP": "1"}


def login(c, email, role=None):
    if c.post("/api/auth/signup", json={"email": email, "password": "password1"}, headers=X).status_code != 200:
        assert c.post("/api/auth/login", json={"email": email, "password": "password1"}, headers=X).status_code == 200
    if role:
        db.x("UPDATE users SET role=? WHERE email=?", (role, email))


def test_metrics_csv_and_backup():
    with TestClient(main.app, headers=X) as o, TestClient(main.app, headers=X) as adm, TestClient(main.app, headers=X) as u:
        login(o, "ops-owner@x.io", "owner")
        login(adm, "ops-admin@x.io", "admin")
        login(u, "ops-user@x.io")
        u.patch("/api/me", json={"name": "=HYPERLINK(\"http://evil\")"})
        for d in (7, 30, 90, 5):
            m = adm.get(f"/api/admin/metrics?days={d}").json()
            assert m["days"] == (d if d in (7, 30, 90) else 30)
            assert {"users", "projects", "jobs", "tokens", "series", "storage", "health"} <= set(m)
            assert m["storage"]["disk_total"] > 0 and m["health"]["version"]
        assert u.get("/api/admin/metrics").status_code == 403

        r = adm.get("/api/admin/export/users.csv")
        assert r.status_code == 200 and r.content.startswith("﻿".encode())
        rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
        assert rows[0][:3] == ["id", "email", "name"]
        assert any(row[2].startswith("'=HYPERLINK") for row in rows[1:])        # chặn công thức khi mở bằng Excel
        assert adm.get("/api/admin/export/secrets.csv").status_code == 404 and u.get("/api/admin/export/jobs.csv").status_code == 403

        assert adm.get("/api/admin/backup").status_code == 403                   # chỉ owner — file chứa khoá mã hoá
        r = o.get("/api/admin/backup")
        z = zipfile.ZipFile(io.BytesIO(r.content))
        names = set(z.namelist())
        assert {"app.db", "fernet.key", "session.key", "RESTORE.txt"} <= names and not any("/build/" in n for n in names)
        with tempfile.TemporaryDirectory() as t:
            z.extract("app.db", t)
            assert sqlite3.connect(os.path.join(t, "app.db")).execute("SELECT COUNT(*) FROM users").fetchone()[0] >= 3


def test_signup_domains_maintenance_and_announcement():
    with TestClient(main.app, headers=X) as o, TestClient(main.app, headers=X) as u, TestClient(main.app, headers=X) as anon:
        login(o, "ops-owner2@x.io", "owner")
        login(u, "ops-user2@x.io")
        try:
            assert o.put("/api/admin/settings", json={"signup_domains": "afi .io"}).status_code == 400
            assert o.put("/api/admin/settings", json={"support_email": "khong-phai-email"}).status_code == 400
            assert o.put("/api/admin/settings", json={"announcement_level": "loud"}).status_code == 400
            assert o.put("/api/admin/settings", json={"signup_domains": "@Afi.io, congty.vn"}).json()["signup_domains"] == "afi.io, congty.vn"
            assert anon.post("/api/auth/signup", json={"email": "la@gmail.com", "password": "password1"}).status_code == 403
            assert anon.post("/api/auth/signup", json={"email": "nv@afi.io", "password": "password1"}).status_code == 200
            inv = o.post("/api/admin/invites", json={"email": "khach@gmail.com"}).json()
            with TestClient(main.app, headers=X) as guest:
                assert guest.post("/api/auth/signup", json={"email": "khach@gmail.com", "password": "password1", "invite": inv["token"]}).status_code == 200

            o.put("/api/admin/settings", json={"maintenance": "1", "announcement": "Bảo trì 22:00–23:00", "support_email": "hotro@afi.io"})
            me = u.get("/api/me").json()
            assert me["maintenance"] and me["announcement"] == "Bảo trì 22:00–23:00" and me["support_email"] == "hotro@afi.io"
            r = u.post("/api/projects", json={"name": "Bị chặn", "idea": "Không tạo được khi đang bảo trì hệ thống."})
            assert r.status_code == 503 and "bảo trì" in r.json()["detail"]
            assert u.get("/api/projects").status_code == 200                       # vẫn xem được
            assert u.patch("/api/me", json={"name": "Vẫn sửa hồ sơ"}).status_code == 200
            assert o.post("/api/projects", json={"name": "Admin vẫn làm", "idea": "Owner vẫn thao tác khi đang bảo trì."}).status_code == 200
        finally:
            o.put("/api/admin/settings", json={"maintenance": "0", "announcement": "", "signup_domains": "", "support_email": ""})
        assert u.post("/api/projects", json={"name": "Hết bảo trì", "idea": "Tạo lại được sau khi tắt bảo trì hệ thống."}).status_code == 200


def test_log_retention_prunes_old_logs():
    old = db.insert("jobs", kind="plan", status="done", log="nhiều dòng log cũ", created="2020-01-01T00:00:00+00:00", finished="2020-01-01T01:00:00+00:00")
    new = db.insert("jobs", kind="plan", status="done", log="log mới", created=db.now(), finished=db.now())
    db.set_setting("log_retention_days", "30")
    try:
        worker.prune_logs()
        assert db.one("SELECT log FROM jobs WHERE id=?", (old,))["log"].startswith("(log đã xoá")
        assert db.one("SELECT log FROM jobs WHERE id=?", (new,))["log"] == "log mới"
    finally:
        db.set_setting("log_retention_days", "0")
