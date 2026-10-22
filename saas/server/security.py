"""Mật khẩu (scrypt), mã hoá API key (Fernet), cookie phiên (itsdangerous)."""
import base64
import hashlib
import hmac
import secrets

from cryptography.fernet import Fernet, InvalidToken
from itsdangerous import BadSignature, URLSafeTimedSerializer

from .config import FERNET_KEY, SESSION_SECRET

_f = Fernet(FERNET_KEY)
_s = URLSafeTimedSerializer(SESSION_SECRET, salt="gp-session")
SESSION_MAX_AGE = 14 * 24 * 3600


def hash_pw(pw: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2 ** 14, r=8, p=1)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(h).decode()


def check_pw(pw: str, stored: str | None) -> bool:
    if not stored or not stored.startswith("scrypt$"):
        return False
    _, salt, h = stored.split("$")
    got = hashlib.scrypt(pw.encode(), salt=base64.b64decode(salt), n=2 ** 14, r=8, p=1)
    return hmac.compare_digest(got, base64.b64decode(h))


def enc(s: str) -> str:
    return _f.encrypt(s.encode()).decode()


def dec(s: str | None) -> str:
    if not s:
        return ""
    try:
        return _f.decrypt(s.encode()).decode()
    except InvalidToken:
        return ""


def hint(key: str) -> str:
    return (key[:4] + "…" + key[-4:]) if len(key) > 12 else "…"


def sign(data: dict) -> str:
    return _s.dumps(data)


def unsign(token: str, max_age=SESSION_MAX_AGE):
    try:
        return _s.loads(token, max_age=max_age)
    except BadSignature:
        return None
