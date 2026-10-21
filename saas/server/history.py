"""Lịch sử phiên bản của từng dự án = một repo git trong thư mục workspace (đúng luật repo: git history là lịch sử hồ sơ).

Mỗi mốc (chạy Plan xong, build lại, sửa số liệu, agent ngoài nộp bài, khôi phục) là một commit. build/ không vào git —
luôn dựng lại được từ SSOT.
"""
import subprocess
import threading
from pathlib import Path

from .config import WORKSPACE

AUTHOR = ("Gen Planner", "noreply@genplanner.local")
_lock = threading.RLock()                     # một thao tác git một lúc (job + người dùng sửa số liệu cùng lúc)


def _git(d: Path, *args, check=True, text=True):
    r = subprocess.run(["git", "-c", "safe.directory=*", "-c", "core.quotepath=off", *args], cwd=d, capture_output=True,
                       text=text, timeout=60, env={"GIT_AUTHOR_NAME": AUTHOR[0], "GIT_AUTHOR_EMAIL": AUTHOR[1],
                                                   "GIT_COMMITTER_NAME": AUTHOR[0], "GIT_COMMITTER_EMAIL": AUTHOR[1],
                                                   "PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(d)})
    if check and r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip()[:300])
    return r


def _ensure(slug):
    d = WORKSPACE / slug
    if not d.exists() or (d / ".git").exists():
        return
    _git(d, "init", "-q", "-b", "main")
    (d / ".gitignore").write_text("build/\n*.tmp\n")
    commit(slug, "Khởi tạo dự án")


def _commit(slug, message, who=None):
    """Ghi một phiên bản nếu SSOT có thay đổi. Trả về mã phiên bản (rev) hoặc None nếu không có gì mới."""
    d = WORKSPACE / slug
    if not (d / ".git").exists():
        if not d.exists():
            return None
        ensure(slug)
    _git(d, "add", "-A")
    if _git(d, "diff", "--cached", "--quiet", check=False).returncode == 0:
        return None
    msg = message if not who else f"{message}\n\nNgười thực hiện: {who}"
    _git(d, "commit", "-q", "-m", msg)
    return _git(d, "rev-parse", "--short", "HEAD").stdout.strip()


def log(slug, n=40):
    d = WORKSPACE / slug
    if not (d / ".git").exists():
        return []
    out = _git(d, "log", f"-{n}", "--date=iso-strict", "--pretty=format:%x1e%h%x1f%ad%x1f%s%x1f%b", "--shortstat", check=False).stdout
    rows = []
    for rec in out.split("\x1e")[1:]:
        rev, date, subject, rest = (rec.split("\x1f", 3) + ["", "", ""])[:4]
        lines = rest.splitlines()
        who = next((x.split(": ", 1)[1] for x in lines if x.startswith("Người thực hiện: ")), None)
        stat = next((x.strip() for x in lines if "changed" in x), "")
        rows.append({"rev": rev.strip(), "date": date, "message": subject, "who": who, "stat": stat})
    return rows


def show(slug, rev):
    """Các file đổi trong phiên bản + diff văn bản (cắt gọn)."""
    d = WORKSPACE / slug
    if not rev.isalnum():
        raise ValueError("rev không hợp lệ")
    files = _git(d, "show", "--name-status", "--pretty=format:", rev).stdout.strip().splitlines()
    patch = _git(d, "show", "--pretty=format:", "--unified=1", "--no-color", rev, "--", ".", ":(exclude)media").stdout
    return {"rev": rev, "files": [f.split("\t", 1) for f in files if "\t" in f], "patch": patch[:40000],
            "truncated": len(patch) > 40000}


def _restore(slug, rev, who=None):
    """Đưa SSOT về đúng trạng thái của phiên bản `rev` (tạo phiên bản mới — không xoá lịch sử)."""
    d = WORKSPACE / slug
    if not rev.isalnum():
        raise ValueError("rev không hợp lệ")
    _git(d, "rev-parse", "--verify", rev + "^{commit}")
    _git(d, "rm", "-r", "-q", "--cached", ".", check=False)
    for f in d.rglob("*"):                                   # xoá file hiện tại (trừ .git, build) rồi lấy lại từ rev
        rel = f.relative_to(d)
        if f.is_file() and rel.parts[0] not in (".git", "build"):
            f.unlink()
    _git(d, "checkout", rev, "--", ".")
    return commit(slug, f"Khôi phục về phiên bản {rev}", who)


def ensure(slug):
    with _lock:
        return _ensure(slug)


def commit(slug, message, who=None):
    with _lock:
        return _commit(slug, message, who)


def restore(slug, rev, who=None):
    with _lock:
        return _restore(slug, rev, who)
