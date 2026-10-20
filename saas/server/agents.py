"""Core agent của hệ thống: chạy CLI agent (Antigravity `agy` mặc định, `claude` dự phòng) dưới tài khoản của owner.

Mỗi agent profile có HOME riêng (saas/data/agents/<id>) → một tài khoản đăng nhập riêng. Đổi tài khoản = chọn profile khác
(hoặc đăng xuất/đăng nhập lại trong terminal của profile). Đăng nhập, xem quota (/usage) chỉ có trong TUI, nên admin dùng
terminal PTY ngay trên giao diện admin.
"""
import fcntl
import json
import os
import pty
import struct
import termios
import re
import select
import signal
import subprocess
import threading
import time
from pathlib import Path

from . import db
from .config import AGENTS_HOME, which
from .security import dec

ENGINES = {
    "agy": {"label": "Antigravity CLI (agy)", "install": "curl -fsSL https://antigravity.google/cli/install.sh | bash",
            "key_env": "GEMINI_API_KEY", "key_label": "Gemini API key",
            "terminal": {"login": (["agy"], []), "usage": (["agy"], ["/usage"]), "credits": (["agy"], ["/credits"]),
                         "logout": (["agy"], ["/logout"])}},
    "claude": {"label": "Claude Code CLI", "install": "npm install -g @anthropic-ai/claude-code",
               "key_env": "ANTHROPIC_API_KEY", "key_label": "Anthropic API key",
               "terminal": {"login": (["claude", "setup-token"], []), "usage": (["claude"], ["/status"]),
                            "logout": (["claude"], ["/logout"])}},
    "demo": {"label": "Demo (không gọi AI — chỉ build template)", "install": "", "terminal": {}},
}
CLAUDE_MODELS = ["sonnet", "opus", "haiku", "claude-sonnet-5-5", "claude-opus-5-5", "claude-haiku-5-5"]
ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07]*(\x07|\x1b\\)|\x1b[()][A-Z0-9]|\x1b[=>]|\r")
CURSOR_RIGHT = re.compile(r"\x1b\[(\d*)C")
URL = re.compile(r"https?://[^\s\"'<>]+")
AUTH_HINT = re.compile(r"authentication required|not signed in|please sign in|authentication failed|invalid api key|api key not valid|api_key_invalid|401", re.I)
QUOTA_HINT = re.compile(r"quota|rate.?limit|429|resource.?exhausted|credits?|usage limit|out of", re.I)


def home(profile) -> Path:
    h = Path(profile["home_dir"] or AGENTS_HOME / str(profile["id"]))
    h.mkdir(parents=True, exist_ok=True)
    return h


def binary(engine):
    return which(engine) if engine in ("agy", "claude") else None


def env_for(profile, home_dir: Path, key: str | None = None):
    """Môi trường cho CLI: HOME riêng; chế độ API key → cài settings provider + biến key."""
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN")}
    env.update(HOME=str(home_dir), BROWSER="echo", NO_BROWSER="1", TERM="xterm-256color")
    env["PATH"] = f"{home_dir}/.local/bin:{Path.home()}/.local/bin:" + env.get("PATH", "")
    if key is None and profile.get("engine") == "claude" and profile.get("auth_mode") == "account" and profile.get("key_enc"):
        env["CLAUDE_CODE_OAUTH_TOKEN"] = dec(profile["key_enc"])     # token từ `claude setup-token`, admin dán vào
    key = key if key is not None else (dec(profile.get("key_enc")) if profile.get("auth_mode") == "api_key" else "")
    if key:
        eng = profile["engine"]
        env[ENGINES[eng]["key_env"]] = key
        if eng == "agy":
            s = home_dir / ".gemini" / "antigravity-cli" / "settings.json"
            s.parent.mkdir(parents=True, exist_ok=True)
            cur = json.loads(s.read_text()) if s.exists() else {}
            cur["modelProvider"] = "gemini"
            s.write_text(json.dumps(cur, indent=2))
    return env


def run(profile, args, timeout=60):
    b = binary(profile["engine"])
    if not b:
        return 127, f"Chưa cài {profile['engine']}. Bấm \"Cài đặt CLI\" hoặc chạy: {ENGINES[profile['engine']]['install']}"
    try:
        r = subprocess.run([b, *args], env=env_for(profile, home(profile)), capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, "Hết thời gian chờ."


def check(profile):
    code, out = run(profile, ["--version"], 30)
    db.update("agent_profiles", profile["id"], version=out.splitlines()[0][:120] if code == 0 and out else None,
              status="ready" if code == 0 else ("not_installed" if code == 127 else "error"))
    return code, out


def list_models(profile):
    if profile["engine"] == "claude":
        models = CLAUDE_MODELS
        out = "Claude Code nhận alias (sonnet/opus/haiku) hoặc model ID đầy đủ."
    elif profile["engine"] == "agy":
        code, out = run(profile, ["models"], 60)
        models = []
        if code == 0:
            for line in out.splitlines():
                tok = line.strip().lstrip("-*•> ").split()
                if tok and re.fullmatch(r"[a-z0-9][a-z0-9._:/-]{2,}", tok[0]) and not tok[0].startswith("http"):
                    models.append(tok[0])
    else:
        return [], "Demo không dùng model."
    db.update("agent_profiles", profile["id"], models=json.dumps(sorted(set(models))))
    return sorted(set(models)), out


def active_profile(exclude=()):
    rows = db.q("SELECT * FROM agent_profiles WHERE enabled=1 ORDER BY is_active DESC, priority, id")
    rows = [r for r in rows if r["id"] not in exclude and r["status"] not in ("quota_exhausted", "needs_login")]
    return rows[0] if rows else None


def tokens_this_month(profile_id):
    r = db.one("SELECT COALESCE(SUM(input_tokens+output_tokens),0) t, COUNT(*) n FROM usage WHERE profile_id=? AND created >= ?",
               (profile_id, db.now()[:7] + "-01"))
    return r["t"], r["n"]


# ------------------------------------------------------------------ PTY terminal (login, /usage, /logout…)
class Terminal:
    def __init__(self, profile, action):
        cmd, keys = ENGINES[profile["engine"]]["terminal"][action]
        b = binary(cmd[0]) if cmd[0] in ("agy", "claude") else cmd[0]
        if not b:
            raise RuntimeError(f"Chưa cài {cmd[0]}.")
        self.buf, self.alive, self.action, self.started = "", True, action, time.time()
        self.master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 50, 400, 0, 0))   # đủ rộng để URL đăng nhập không bị xuống dòng
        self.proc = subprocess.Popen([b, *cmd[1:]], stdin=slave, stdout=slave, stderr=slave, env=env_for(profile, home(profile)),
                                     cwd=str(home(profile)), start_new_session=True, close_fds=True)
        os.close(slave)
        threading.Thread(target=self._read, daemon=True).start()
        if keys:
            threading.Thread(target=self._type_later, args=(keys,), daemon=True).start()

    def _type_later(self, keys):
        time.sleep(5)
        for k in keys:
            self.send(k + "\r")
            time.sleep(1.5)

    def _read(self):
        while True:
            try:
                r, _, _ = select.select([self.master], [], [], 0.5)
                if r:
                    data = os.read(self.master, 65536)
                    if not data:
                        break
                    self.buf = (self.buf + data.decode("utf-8", "replace"))[-60000:]
                elif self.proc.poll() is not None:
                    break
            except OSError:
                break
        self.alive = False

    def send(self, text):
        if self.alive:
            os.write(self.master, text.encode())

    def stop(self):
        if self.proc.poll() is None:
            try:
                os.killpg(self.proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        self.alive = False

    def view(self):
        text = ANSI.sub("", CURSOR_RIGHT.sub(lambda m: " " * int(m.group(1) or 1), self.buf))
        return {"output": text[-20000:], "urls": sorted(set(u.rstrip(".,)") for u in URL.findall(text)))[-5:],
                "alive": self.alive and self.proc.poll() is None, "action": self.action}


TERMINALS: dict[int, Terminal] = {}


def terminal_start(profile, action):
    old = TERMINALS.pop(profile["id"], None)
    if old:
        old.stop()
    if action not in ENGINES[profile["engine"]]["terminal"]:
        raise RuntimeError("Engine này không có thao tác đó.")
    t = TERMINALS[profile["id"]] = Terminal(profile, action)
    return t


def terminal_finish(profile_id):
    """Khi đóng terminal /usage → lưu văn bản quota để admin xem lại."""
    t = TERMINALS.get(profile_id)
    if t and t.action in ("usage", "credits"):
        db.update("agent_profiles", profile_id, quota_text=t.view()["output"][-4000:], quota_checked=db.now())
    if t and t.action == "login":
        db.update("agent_profiles", profile_id, status="ready")     # sau khi đăng nhập, cho job thử lại tài khoản này
    if t:
        t.stop()
