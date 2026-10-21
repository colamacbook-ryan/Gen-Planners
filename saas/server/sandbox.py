"""Cô lập core agent khỏi bí mật của máy chủ.

Agent có quyền shell và đọc dữ liệu do người dùng viết (ý tưởng, câu trả lời, điểm chốt) — tức là có thể bị
prompt-injection. Vì vậy agent không được thấy: app.db, khoá phiên, khoá mã hoá, HOME của tài khoản agent khác,
dự án của người dùng khác. Khi máy chủ chạy bằng root và có user hệ thống GP_AGENT_USER (mặc định `gpagent`),
mỗi job chạy dưới user đó, chỉ được trao quyền vào đúng thư mục dự án + HOME của job. Không có user đó → chạy
cùng quyền máy chủ và admin thấy cảnh báo.
"""
import os
import pwd
import re
import stat
from pathlib import Path

from .config import AGENTS_HOME, DATA, HISTORY, JOBS_HOME, WORKSPACE

AGENT_USER = os.environ.get("GP_AGENT_USER", "gpagent")
SECRET_ENV = re.compile(r"^GP_|SECRET|PASSWORD|_KEY$|_TOKEN$|^AWS_|^GOOGLE_APPLICATION", re.I)


def agent_ids():
    """(uid, gid) của user chạy agent, hoặc None nếu không cô lập được."""
    if os.geteuid() != 0:
        return None
    try:
        pw = pwd.getpwnam(AGENT_USER)
    except KeyError:
        return None
    return pw.pw_uid, pw.pw_gid


def status():
    ids = agent_ids()
    if ids:
        return {"enabled": True, "user": AGENT_USER, "hint": f"Agent chạy dưới user `{AGENT_USER}`, chỉ thấy thư mục dự án của job."}
    why = "máy chủ không chạy bằng root" if os.geteuid() != 0 else f"chưa có user hệ thống `{AGENT_USER}`"
    return {"enabled": False, "user": None,
            "hint": f"Agent đang chạy cùng quyền máy chủ ({why}). Người dùng có thể lừa agent đọc khoá bí mật qua nội dung dự án. "
                    f"Khắc phục: chạy máy chủ bằng root trong container và tạo user: `useradd -r -m {AGENT_USER}` (Dockerfile đã có sẵn)."}


def lock_down():
    """Quyền mặc định: dữ liệu máy chủ chỉ root đọc được; thư mục cha chỉ cho đi qua (không liệt kê)."""
    if os.geteuid() != 0:
        return
    for d in (DATA, WORKSPACE.parent, WORKSPACE, AGENTS_HOME, JOBS_HOME, HISTORY):
        d.mkdir(parents=True, exist_ok=True)
        os.chmod(d, 0o711)
    for f in DATA.iterdir():
        if f.is_file():
            os.chmod(f, 0o600)
    for d in list(WORKSPACE.iterdir()) + list(AGENTS_HOME.iterdir()) + list(HISTORY.iterdir()):
        if d.is_dir():
            os.chmod(d, 0o700)


def _chown_tree(path: Path, uid, gid):
    os.chown(path, uid, gid)
    for root, dirs, files in os.walk(path):
        for n in dirs + files:
            try:
                os.lchown(os.path.join(root, n), uid, gid)
            except FileNotFoundError:
                pass


def grant(*paths):
    """Trao quyền thư mục cho user agent trước khi job chạy."""
    ids = agent_ids()
    if not ids:
        return
    for p in paths:
        _chown_tree(Path(p), *ids)
        os.chmod(p, 0o700)


def revoke(*paths):
    """Thu lại sau job: trả về root, 700 — job sau của người khác không đọc được."""
    if not agent_ids():
        return
    for p in paths:
        if Path(p).exists():
            _chown_tree(Path(p), 0, 0)
            os.chmod(p, 0o700)


def strip_links(path):
    """Xoá symlink và file đặc biệt (FIFO, socket, device) agent để lại — máy chủ đọc/ghi/nén dự án không bị dẫn ra ngoài."""
    removed = []
    for root, dirs, files in os.walk(path):                      # os.walk không đi theo symlink thư mục
        for n in dirs + files:
            f = os.path.join(root, n)
            st = os.lstat(f)
            if stat.S_ISLNK(st.st_mode) or not (stat.S_ISREG(st.st_mode) or stat.S_ISDIR(st.st_mode)):
                os.unlink(f)
                removed.append(os.path.relpath(f, path))
        dirs[:] = [n for n in dirs if os.path.isdir(os.path.join(root, n)) and not os.path.islink(os.path.join(root, n))]
    return removed


def clean_env(env: dict) -> dict:
    """Bỏ mọi biến môi trường bí mật của máy chủ; giữ lại khoá mà chính job cần (đặt sau hàm này)."""
    return {k: v for k, v in env.items() if not SECRET_ENV.search(k)}


def popen_kwargs():
    ids = agent_ids()
    return {"user": ids[0], "group": ids[1], "extra_groups": []} if ids else {}
