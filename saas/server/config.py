"""Đường dẫn & bí mật chạy lúc runtime. Không có gì ở đây được commit: saas/data/ nằm trong .gitignore."""
import os
import secrets
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # repo Gen-Planners
SAAS = ROOT / "saas"
DATA = Path(os.environ.get("GP_DATA") or SAAS / "data")
WORKSPACE = DATA / "workspace" / "projects"         # dự án của user (GP_PROJECTS cho gen.py)
AGENTS_HOME = DATA / "agents"                       # mỗi agent profile một HOME riêng → một tài khoản
JOBS_HOME = DATA / "jobs"                           # HOME tạm cho job chạy bằng key của user
DB_PATH = DATA / "app.db"
for d in (DATA, WORKSPACE, AGENTS_HOME, JOBS_HOME):
    d.mkdir(parents=True, exist_ok=True)


def _secret(name: str, env: str, gen) -> bytes:
    if os.environ.get(env):
        return os.environ[env].encode()
    p = DATA / name
    if not p.exists():
        p.write_bytes(gen())
        p.chmod(0o600)
    return p.read_bytes().strip()


def _fernet_key():
    from cryptography.fernet import Fernet
    return Fernet.generate_key()


SESSION_SECRET = _secret("session.key", "GP_SESSION_SECRET", lambda: secrets.token_urlsafe(48).encode())
FERNET_KEY = _secret("fernet.key", "GP_FERNET_KEY", _fernet_key)
COOKIE_SECURE = os.environ.get("GP_COOKIE_SECURE", "0") == "1"


def which(name: str):
    """Tìm CLI cả ở PATH lẫn nơi installer hay đặt (~/.local/bin)."""
    return shutil.which(name) or next((str(p) for p in (Path.home() / ".local/bin" / name, Path("/usr/local/bin") / name) if p.exists()), None)
