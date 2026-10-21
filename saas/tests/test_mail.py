"""Email qua SMTP thật (máy chủ SMTP tối giản chạy trong test): quên/đặt lại mật khẩu, lời mời, báo Plan xong, gửi thử."""
import email
import email.policy
import os
import re
import socketserver
import tempfile
import threading
import time
import urllib.parse

os.environ.setdefault("GP_DATA", tempfile.mkdtemp(prefix="gp-test-"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from saas.server import db, main, mail  # noqa: E402

X = {"X-GP": "1"}
INBOX = []


class SMTPSink(socketserver.StreamRequestHandler):
    """Đủ giao thức SMTP cho smtplib: EHLO/MAIL/RCPT/DATA/QUIT — lưu thư vào INBOX."""
    def handle(self):
        w = lambda s: (self.wfile.write((s + "\r\n").encode()), self.wfile.flush())  # noqa: E731
        w("220 sink")
        rcpt = []
        while True:
            line = self.rfile.readline().decode(errors="replace").strip()
            cmd = line[:4].upper()
            if cmd in ("EHLO", "HELO"):
                w("250 sink")
            elif cmd == "MAIL":
                rcpt = []
                w("250 ok")
            elif cmd == "RCPT":
                rcpt.append(re.search(r"<(.*)>", line).group(1))
                w("250 ok")
            elif cmd == "DATA":
                w("354 go")
                data = []
                while (ln := self.rfile.readline()) not in (b".\r\n", b""):
                    data.append(ln[1:] if ln.startswith(b"..") else ln)
                INBOX.append((rcpt, email.message_from_bytes(b"".join(data), policy=email.policy.default)))
                w("250 queued")
            elif cmd in ("QUIT", ""):
                w("221 bye")
                return
            else:
                w("250 ok")


@pytest.fixture(scope="module")
def smtp():
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), SMTPSink)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    for k, v in {"smtp_host": "127.0.0.1", "smtp_port": str(srv.server_address[1]), "smtp_tls": "none", "smtp_from": "noreply@gp.test",
                 "smtp_user": "", "public_base_url": "https://plan.test"}.items():
        db.set_setting(k, v)
    yield INBOX
    for k in ("smtp_host", "smtp_from", "public_base_url"):
        db.set_setting(k, "")
    srv.shutdown()


def wait_mail(to, n=1):
    for _ in range(100):
        got = [m for r, m in INBOX if to in r]
        if len(got) >= n:
            return got[-1]
        time.sleep(0.05)
    raise AssertionError(f"không thấy email tới {to}")


def body(m):
    return next(p.get_content() for p in m.walk() if p.get_content_type() == "text/plain")


def login(c, e, pw="password1"):
    if c.post("/api/auth/signup", json={"email": e, "password": pw}, headers=X).status_code != 200:
        assert c.post("/api/auth/login", json={"email": e, "password": pw}, headers=X).status_code == 200


def test_forgot_and_reset_password(smtp):
    with TestClient(main.app, headers=X) as c, TestClient(main.app, headers=X) as old:
        login(c, "forget@x.io")
        login(old, "forget@x.io")
        r = c.post("/api/auth/forgot", json={"email": "khong-co@x.io"}).json()
        same = c.post("/api/auth/forgot", json={"email": "forget@x.io"}).json()
        assert r["message"] == same["message"]                                  # không lộ email nào có tài khoản
        m = wait_mail("forget@x.io")
        assert not [x for rr, x in INBOX if "khong-co@x.io" in rr]
        assert "Đặt lại mật khẩu" in m["Subject"]
        token = urllib.parse.unquote(re.search(r"reset=([^\s]+)", body(m)).group(1))
        assert c.post("/api/auth/reset", json={"token": token, "password": "ngan"}).status_code == 400
        assert c.post("/api/auth/reset", json={"token": token, "password": "matkhau-moi-1"}).status_code == 200
        assert c.post("/api/auth/reset", json={"token": token, "password": "matkhau-moi-2"}).status_code == 400     # dùng một lần
        assert old.get("/api/me").status_code == 401                                # phiên cũ bị đăng xuất
        assert c.post("/api/auth/login", json={"email": "forget@x.io", "password": "matkhau-moi-1"}).status_code == 200
        # link cũ hết hiệu lực khi xin link mới; link hết hạn bị từ chối
        c.post("/api/auth/forgot", json={"email": "forget@x.io"})
        t1 = urllib.parse.unquote(re.search(r"reset=([^\s]+)", body(wait_mail("forget@x.io", 2))).group(1))
        c.post("/api/auth/forgot", json={"email": "forget@x.io"})
        wait_mail("forget@x.io", 3)
        assert c.post("/api/auth/reset", json={"token": t1, "password": "matkhau-moi-3"}).status_code == 400
        db.x("UPDATE password_resets SET expires='2000-01-01T00:00:00+00:00' WHERE used IS NULL")
        t3 = urllib.parse.unquote(re.search(r"reset=([^\s]+)", body(wait_mail("forget@x.io", 3))).group(1))
        assert c.post("/api/auth/reset", json={"token": t3, "password": "matkhau-moi-3"}).status_code == 400


def test_invite_email_job_notice_and_test_send(smtp):
    with TestClient(main.app, headers=X) as o, TestClient(main.app, headers=X) as u:
        login(o, "mail-owner@x.io")
        db.x("UPDATE users SET role='owner' WHERE email='mail-owner@x.io'")
        r = o.post("/api/admin/invites", json={"email": "khach-moi@x.io", "send_email": True}).json()
        assert r["emailed"]
        m = wait_mail("khach-moi@x.io")
        assert r["token"] in urllib.parse.unquote(body(m)) and "https://plan.test/login?invite=" in body(m)
        html = next(p.get_content() for p in m.walk() if p.get_content_type() == "text/html")
        assert "<script" not in html

        assert o.post("/api/admin/settings/test-email", json={"to": "kiemtra@x.io"}).json()["ok"]
        assert "Email hoạt động" in body(wait_mail("kiemtra@x.io"))
        db.set_setting("allow_demo_engine", "1")
        login(u, "notify@x.io")
        slug = u.post("/api/projects", json={"name": "Báo <b>xong</b>", "idea": "Dự án để thử email báo Plan chạy xong."}).json()["slug"]
        jid = u.post(f"/api/projects/{slug}/run", json={"billing": "demo", "force": True}).json()["job_id"]
        m = wait_mail("notify@x.io")
        assert "đã sẵn sàng" in m["Subject"] and f"https://plan.test/app#p={slug}&t=dossier" in body(m)
        assert "<b>xong</b>" not in next(p.get_content() for p in m.walk() if p.get_content_type() == "text/html")   # tên dự án được escape
        u.patch("/api/me", json={"prefs": {"notify_job": False}})
        n = len(INBOX)
        for _ in range(60):
            if u.get(f"/api/jobs/{jid}").json()["status"] == "done":
                break
            time.sleep(0.1)
        jid2 = u.post(f"/api/projects/{slug}/run", json={"billing": "demo", "force": True}).json()["job_id"]
        for _ in range(100):
            if u.get(f"/api/jobs/{jid2}").json()["status"] not in ("queued", "starting", "running"):
                break
            time.sleep(0.1)
        time.sleep(0.3)
        assert len(INBOX) == n                                                     # người dùng tắt thông báo → không gửi


def test_no_smtp_degrades_gracefully():
    db.set_setting("smtp_host", "")
    with TestClient(main.app, headers=X) as c:
        r = c.post("/api/auth/forgot", json={"email": "ai@x.io"}).json()
        assert r["mail"] is False and "admin" in r["message"]
        assert mail.send("a@x.io", "s", "t") is False
