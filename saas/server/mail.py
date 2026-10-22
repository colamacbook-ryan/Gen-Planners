"""Gửi email qua SMTP do owner cấu hình (Cài đặt hệ thống → Email). Không cấu hình → các tính năng email tự tắt êm.

Dùng cho: đặt lại mật khẩu, gửi lời mời, báo Plan chạy xong. Gửi ở luồng nền để request không phải đợi máy chủ mail.
"""
import html as _html
import smtplib
import ssl
import threading
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from . import db
from .security import dec

TLS_MODES = ("starttls", "ssl", "none")


def configured():
    return bool(db.setting("smtp_host") and db.setting("smtp_from"))


def _send(to, subject, text, html=None):
    msg = EmailMessage()
    msg["From"] = formataddr((db.setting("site_name") or "Gen Planner", db.setting("smtp_from")))
    msg["To"] = to
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain=db.setting("smtp_from").split("@")[-1])
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    host, port, mode = db.setting("smtp_host"), int(db.setting("smtp_port") or 587), db.setting("smtp_tls") or "starttls"
    ctx = ssl.create_default_context()
    smtp = smtplib.SMTP_SSL(host, port, timeout=20, context=ctx) if mode == "ssl" else smtplib.SMTP(host, port, timeout=20)
    try:
        if mode == "starttls":
            smtp.starttls(context=ctx)
        user, pw = db.setting("smtp_user"), db.setting("smtp_password_enc")
        if user:
            smtp.login(user, dec(pw) if pw else "")
        smtp.send_message(msg)
    finally:
        try:
            smtp.quit()
        except smtplib.SMTPException:
            pass


def send(to, subject, text, html=None, wait=False):
    """Gửi một email. wait=False: chạy nền, lỗi chỉ ghi nhật ký. wait=True: trả (ok, lỗi) — dùng cho nút "Gửi thử"."""
    if not configured() or not to:
        return (False, "Chưa cấu hình SMTP") if wait else False

    def job():
        try:
            _send(to, subject, text, html)
            db.audit(None, "mail_sent", to, {"subject": subject})
            return True, None
        except (OSError, smtplib.SMTPException) as e:
            db.audit(None, "mail_failed", to, {"subject": subject, "error": str(e)[:200]})
            return False, f"{type(e).__name__}: {e}"[:300]
    if wait:
        return job()
    threading.Thread(target=job, daemon=True).start()
    return True


def layout(title, body_text, button=None, url=None):
    """Bản text + HTML đơn giản, đọc tốt trên mọi trình mail."""
    site = db.setting("site_name") or "Gen Planner"
    text = f"{title}\n\n{body_text}\n" + (f"\n{button}: {url}\n" if url else "") + f"\n— {site}"
    e = _html.escape                                     # nội dung có thể chứa tên dự án do người dùng đặt
    btn = (f'<p><a href="{e(url)}" style="display:inline-block;background:#0e7a6a;color:#fff;padding:10px 18px;border-radius:8px;'
           f'text-decoration:none;font-weight:600">{e(button)}</a></p><p style="color:#667;font-size:12px">Hoặc mở: {e(url)}</p>') if url else ""
    paras = "".join(f"<p>{e(p)}</p>" for p in body_text.split("\n\n"))
    html = (f'<div style="font-family:system-ui,Segoe UI,sans-serif;max-width:560px;margin:auto;color:#1b2430">'
            f'<h2 style="font-weight:600">{e(title)}</h2>{paras}{btn}<p style="color:#667;font-size:12px">— {e(site)}</p></div>')
    return text, html
