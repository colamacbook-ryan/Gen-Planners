"""Lịch sử phiên bản của từng dự án = một repo git (đúng luật repo: git history là lịch sử hồ sơ).

Mỗi mốc (chạy Plan xong, build lại, sửa số liệu, agent ngoài nộp bài, khôi phục) là một commit. build/ không vào git —
luôn dựng lại được từ SSOT.

Git dir nằm ở GP_DATA/history/<slug>.git (root sở hữu), KHÔNG nằm trong thư mục dự án: agent có quyền ghi thư mục dự án,
nếu .git ở đó nó có thể cài hook / core.fsmonitor và chạy lệnh bằng quyền máy chủ ở lần commit kế tiếp.
"""
import os
import shutil
import subprocess
import threading
from pathlib import Path

from .config import HISTORY, WORKSPACE

AUTHOR = ("Gen Planner", "noreply@genplanner.local")
_lock = threading.RLock()                     # một thao tác git một lúc (job + người dùng sửa số liệu cùng lúc)
HARDEN = ["-c", "core.fsmonitor=", "-c", "core.hooksPath=/dev/null", "-c", "core.symlinks=false", "-c", "core.quotepath=off",
          "-c", "safe.directory=*", "-c", "protocol.allow=never"]


def git_dir(slug) -> Path:
    return HISTORY / f"{slug}.git"


def _git(slug, *args, check=True, text=True):
    d = WORKSPACE / slug
    r = subprocess.run(["git", "--git-dir", str(git_dir(slug)), "--work-tree", str(d), *HARDEN, *args], cwd=d, capture_output=True,
                       text=text, timeout=60, env={"GIT_AUTHOR_NAME": AUTHOR[0], "GIT_AUTHOR_EMAIL": AUTHOR[1],
                                                   "GIT_COMMITTER_NAME": AUTHOR[0], "GIT_COMMITTER_EMAIL": AUTHOR[1],
                                                   "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
                                                   "PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(HISTORY)})
    if check and r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip()[:300])
    return r


def _ensure(slug):
    d, g = WORKSPACE / slug, git_dir(slug)
    if not d.exists():
        return
    legacy = d / ".git"                                   # bản cũ để .git trong thư mục dự án: dời ra, bỏ config/hook không tin được
    if legacy.is_dir() and not legacy.is_symlink() and not g.exists():
        shutil.move(str(legacy), str(g))
        shutil.rmtree(g / "hooks", ignore_errors=True)
        (g / "config").write_text("[core]\n\trepositoryformatversion = 0\n\tbare = false\n")
    if legacy.exists() or legacy.is_symlink():
        shutil.rmtree(legacy) if legacy.is_dir() and not legacy.is_symlink() else legacy.unlink()
    if g.exists():
        os.chmod(g, 0o700)                                # agent (user khác) không đọc được lịch sử dự án khác
    if not g.exists():
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(g)], check=True, capture_output=True,
                       env={"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(HISTORY), "GIT_CONFIG_NOSYSTEM": "1"})
        (g / "config").write_text("[core]\n\trepositoryformatversion = 0\n\tbare = false\n")
        shutil.rmtree(g / "hooks", ignore_errors=True)
        os.chmod(g, 0o700)
        (g / "info").mkdir(exist_ok=True)
        (g / "info" / "exclude").write_text("build/\n*.tmp\n.git\n.gitignore\n")
        _commit(slug, "Khởi tạo dự án")
    else:
        (g / "info").mkdir(exist_ok=True)
        (g / "info" / "exclude").write_text("build/\n*.tmp\n.git\n.gitignore\n")


def _commit(slug, message, who=None):
    """Ghi một phiên bản nếu SSOT có thay đổi. Trả về mã phiên bản (rev) hoặc None nếu không có gì mới."""
    d = WORKSPACE / slug
    if not d.exists():
        return None
    if not git_dir(slug).exists() or (d / ".git").exists():
        _ensure(slug)
    _git(slug, "add", "-A")
    if _git(slug, "diff", "--cached", "--quiet", check=False).returncode == 0:
        return None
    msg = message if not who else f"{message}\n\nNgười thực hiện: {who}"
    _git(slug, "commit", "-q", "-m", msg)
    return _git(slug, "rev-parse", "--short", "HEAD").stdout.strip()


def rev(slug):
    if not git_dir(slug).exists():
        return None
    r = _git(slug, "rev-parse", "--short", "HEAD", check=False)
    return r.stdout.strip() if r.returncode == 0 else None


def log(slug, n=40):
    if not git_dir(slug).exists():
        return []
    out = _git(slug, "log", f"-{n}", "--date=iso-strict", "--pretty=format:%x1e%h%x1f%ad%x1f%s%x1f%b", "--shortstat", check=False).stdout
    rows = []
    for rec in out.split("\x1e")[1:]:
        rv, date, subject, rest = (rec.split("\x1f", 3) + ["", "", ""])[:4]
        lines = rest.splitlines()
        who = next((x.split(": ", 1)[1] for x in lines if x.startswith("Người thực hiện: ")), None)
        stat = next((x.strip() for x in lines if "changed" in x), "")
        rows.append({"rev": rv.strip(), "date": date, "message": subject, "who": who, "stat": stat})
    return rows


def _check_rev(rv):
    if not rv.isalnum():                      # chặn cả tham số git (vd "--output=…")
        raise ValueError("rev không hợp lệ")


def show(slug, rv):
    """Các file đổi trong phiên bản + diff văn bản (cắt gọn)."""
    _check_rev(rv)
    files = _git(slug, "show", "--name-status", "--pretty=format:", rv).stdout.strip().splitlines()
    patch = _git(slug, "show", "--pretty=format:", "--unified=1", "--no-color", rv, "--", ".", ":(exclude)media").stdout
    return {"rev": rv, "files": [f.split("\t", 1) for f in files if "\t" in f], "patch": patch[:40000],
            "truncated": len(patch) > 40000}


def _restore(slug, rv, who=None):
    """Đưa SSOT về đúng trạng thái của phiên bản `rv` (tạo phiên bản mới — không xoá lịch sử)."""
    _check_rev(rv)
    d = WORKSPACE / slug
    _git(slug, "rev-parse", "--verify", rv + "^{commit}")
    _git(slug, "rm", "-r", "-q", "--cached", ".", check=False)
    for f in list(d.rglob("*")):                             # xoá file hiện tại (trừ build) rồi lấy lại từ rv
        rel = f.relative_to(d)
        if (f.is_file() or f.is_symlink()) and rel.parts[0] != "build":
            f.unlink()
    _git(slug, "checkout", rv, "--", ".")
    return commit(slug, f"Khôi phục về phiên bản {rv}", who)


def ensure(slug):
    with _lock:
        return _ensure(slug)


def commit(slug, message, who=None):
    with _lock:
        return _commit(slug, message, who)


def restore(slug, rv, who=None):
    with _lock:
        return _restore(slug, rv, who)


def remove(slug):
    with _lock:
        shutil.rmtree(git_dir(slug), ignore_errors=True)
