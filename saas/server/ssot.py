"""Thao tác trên SSOT của một dự án trong workspace: sửa giả định, kiểm link nguồn, đóng gói, đọc tiến độ stage.

Sửa giả định = sửa đúng một dòng `value:` trong assumptions.yaml (giữ comment và định dạng), đúng luật SSOT số 4.
"""
import concurrent.futures as cf
import copy
import io
import ipaddress
import socket
import urllib.parse
import json
import math
import os
import re
import zipfile
from pathlib import Path

import httpx
import yaml

from .config import ROOT, WORKSPACE


class SSOTError(Exception):
    pass


def _validate_model(A):
    """gen.validate_model (cùng luật với `gen.py check`) — nạp lười để server không phụ thuộc gen.py khi khởi động."""
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import gen
    return gen.validate_model(A)[0]


def project_dir(slug: str) -> Path:
    return WORKSPACE / slug


def safe_path(slug, rel) -> Path:
    """Đường dẫn trong dự án, không đi qua symlink nào và không thoát ra ngoài thư mục dự án."""
    root = project_dir(slug)
    f = root
    for part in Path(rel).parts:
        if part in ("..", "/") or part.startswith("/"):
            raise SSOTError("Đường dẫn không hợp lệ")
        f = f / part
        if f.is_symlink():
            raise SSOTError("Đường dẫn là symlink — không được phép")
    if not f.resolve().is_relative_to(root.resolve()):
        raise SSOTError("Đường dẫn ra ngoài dự án")
    return f


def write_nofollow(f: Path, data: bytes):
    fd = os.open(f, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o644)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)


def load(p: Path):
    return yaml.safe_load(p.read_text()) or {} if p.exists() else {}


# ------------------------------------------------------------------ giả định
def read_assumptions(slug):
    d = project_dir(slug)
    A = load(d / "assumptions.yaml")
    meta = A.get("meta", {})
    rows = [{"id": k, "label": v.get("label") or k, "value": v.get("value"), "unit": v.get("unit"), "status": v.get("status"),
             "confidence": v.get("confidence"), "source": v.get("source") or [], "note": v.get("note")}
            for k, v in (A.get("assumptions") or {}).items() if isinstance(v, dict)]
    return {"meta": {"start_year": meta.get("start_year"), "years": meta.get("years"), "unit_label": meta.get("unit_label")}, "assumptions": rows}


def _fmt(v):
    if isinstance(v, list):
        return "[" + ", ".join(_fmt(x) for x in v) + "]"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return json.dumps(v) if isinstance(v, str) else str(v)


def _coerce(new, old):
    """Giá trị mới phải cùng hình dạng với giá trị cũ: số ↔ số, list ↔ list cùng độ dài."""
    def num(x):
        if isinstance(x, bool) or not isinstance(x, (int, float, str)):
            raise SSOTError("Giá trị phải là số")
        try:
            f = float(str(x).replace(",", ".").strip())
        except ValueError:
            raise SSOTError(f"Không đọc được số: {x}") from None
        if not math.isfinite(f):
            raise SSOTError(f"Không đọc được số: {x}")
        return int(f) if f.is_integer() else f
    if isinstance(old, list):
        items = new if isinstance(new, list) else [s for s in re.split(r"[;\s]+", str(new).strip()) if s]
        if len(items) != len(old):
            raise SSOTError(f"Cần đúng {len(old)} giá trị (mỗi năm một số)")
        return [num(x) for x in items]
    if isinstance(old, (int, float)) and not isinstance(old, bool):
        return num(new)
    raise SSOTError("Giả định này không phải số — sửa trực tiếp trong assumptions.yaml")


def set_value(slug, key, new, status=None):
    p = project_dir(slug) / "assumptions.yaml"
    A = load(p)
    cur = (A.get("assumptions") or {}).get(key)
    if not isinstance(cur, dict):
        raise SSOTError(f"Không có giả định {key}")
    old = cur.get("value")
    value = _coerce(new, old)
    if status and status not in ("placeholder", "estimate", "verified"):
        raise SSOTError("Trạng thái không hợp lệ")
    if status == "verified" and not cur.get("source"):
        raise SSOTError("Chỉ đánh 'verified' khi giả định có nguồn trong evidence.yaml")
    expected = copy.deepcopy(A)                                  # bản sao sâu: chỉ đúng một giá trị (và trạng thái) được đổi
    expected["assumptions"][key]["value"] = value
    if status:
        expected["assumptions"][key]["status"] = status
    new_errs = set(_validate_model(expected)) - set(_validate_model(A))   # chỉ chặn lỗi do chính lần sửa này gây ra
    if new_errs:
        raise SSOTError("Giá trị này làm model sai: " + "; ".join(sorted(new_errs)))
    text = p.read_text()
    edited = _edit_line(text, key, value, status)
    try:
        ok = edited is not None and yaml.safe_load(edited) == expected
    except yaml.YAMLError:
        ok = False
    if ok:
        p.write_text(edited)                                      # giữ nguyên comment và định dạng
    else:                                                         # dòng không sửa an toàn được: ghi lại cả file (mất comment)
        p.write_text(yaml.safe_dump(expected, allow_unicode=True, sort_keys=False))
    return {"id": key, "label": cur.get("label") or key, "old": old, "value": value}


def _edit_line(text, key, value, status):
    """Sửa `value:` (và `status:`) trên đúng dòng flow-mapping của giả định, chỉ trong khối `assumptions:`."""
    lines, inside = text.split("\n"), False
    head = re.compile(rf"^(\s+){re.escape(key)}:\s*\{{")
    for i, line in enumerate(lines):
        if re.match(r"^\S", line):                            # khoá cấp cao nhất
            inside = line.startswith("assumptions:")
            continue
        if inside and head.match(line):
            # chỉ khớp `value:` đứng ngay sau `{` hoặc `,` — không khớp chữ "value:" nằm trong label/note
            new = re.sub(r"([{,]\s*value:\s*)(\[[^\]]*\]|[^,}]+)", lambda m: m.group(1) + _fmt(value), line, count=1)
            if status:
                new = re.sub(r"([{,]\s*status:\s*)([^,}]+)", lambda m: m.group(1) + status, new, count=1)
            lines[i] = new
            return "\n".join(lines)
    return None


def kpi(slug):
    f = project_dir(slug) / "build" / "export" / "project.json"
    return json.loads(f.read_text()).get("kpi") if f.exists() else None


# ------------------------------------------------------------------ kiểm tra link nguồn
def collect_urls(slug):
    d = project_dir(slug)
    found = {}

    def walk(x, where):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in ("url", "link", "href") and isinstance(v, str) and v.startswith("http"):
                    found.setdefault(v, {"url": v, "where": where, "title": x.get("title") or x.get("name") or ""})
                else:
                    walk(v, where)
        elif isinstance(x, list):
            for v in x:
                walk(v, where)
    for name in ("evidence.yaml", "story.yaml", "products.yaml"):
        walk(load(d / name), name)
    return list(found.values())


def _public(url):
    """Chỉ cho phép http(s) tới địa chỉ công khai — không để nội dung dự án dò mạng nội bộ của máy chủ."""
    u = urllib.parse.urlsplit(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        return False
    try:
        infos = socket.getaddrinfo(u.hostname, u.port or (443 if u.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return True                                     # không phân giải được: để httpx báo lỗi bình thường
    for *_, addr in infos:
        ip = ipaddress.ip_address(addr[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            return False
    return True


def _probe(client, url, hops=5):
    try:
        for _ in range(hops):
            if not _public(url):
                return {"code": None, "ok": False, "blocked": False, "error": "địa chỉ nội bộ — bỏ qua"}
            r = client.head(url)
            if r.status_code in (403, 405, 406, 400, 404) or r.status_code >= 500:   # nhiều site không trả lời HEAD đúng
                r = client.get(url, headers={"Range": "bytes=0-2048"})
            if r.is_redirect and r.headers.get("location"):
                url = urllib.parse.urljoin(url, r.headers["location"])
                continue
            code = r.status_code
            return {"code": code, "ok": code < 400, "blocked": code in (401, 403, 406, 429)}
        return {"code": None, "ok": False, "blocked": False, "error": "chuyển hướng quá nhiều"}
    except httpx.HTTPError as e:
        return {"code": None, "ok": False, "blocked": False, "error": type(e).__name__}


def link_check(slug, workers=12):
    items = collect_urls(slug)
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
               "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "vi,en;q=0.8"}
    with httpx.Client(timeout=12, follow_redirects=False, headers=headers) as client, cf.ThreadPoolExecutor(workers) as ex:
        for it, res in zip(items, ex.map(lambda i: _probe(client, i["url"]), items)):
            it.update(res)
    out = {"checked": len(items), "ok": sum(i["ok"] for i in items), "blocked": sum(i["blocked"] for i in items),
           "broken": [i for i in items if not i["ok"] and not i["blocked"]], "items": items}
    f = project_dir(slug) / "build" / "linkcheck.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(out, ensure_ascii=False))
    return out


def link_summary(slug):
    f = project_dir(slug) / "build" / "linkcheck.json"
    if not f.exists():
        return None
    j = json.loads(f.read_text())
    return {k: j[k] for k in ("checked", "ok", "blocked")} | {"broken": j["broken"][:30]}


# ------------------------------------------------------------------ đóng gói & tiến độ
BUNDLE_FILES = ["idea.md", "brief.md", "project.yaml", "assumptions.yaml", "evidence.yaml", "story.yaml", "datasets.yaml",
                "products.yaml", "deck.md"]
BUNDLE_DIRS = ["sections", "research", "media"]
BUILD_FILES = ["business-plan.docx", "deck.pptx", "financials.xlsx", "business-plan.md"]


def _plain(root: Path, f: Path):
    """Không thành phần nào từ root tới f là symlink — zip không được kéo file ngoài dự án vào."""
    rel = f.relative_to(root)
    return not any((root / Path(*rel.parts[:i + 1])).is_symlink() for i in range(len(rel.parts)))


def bundle(slug) -> bytes:
    d = project_dir(slug)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in BUILD_FILES:
            if (d / "build" / f).is_file() and _plain(d, d / "build" / f):
                z.write(d / "build" / f, f"{slug}/{f}")
        for f in BUNDLE_FILES:
            if (d / f).is_file() and _plain(d, d / f):
                z.write(d / f, f"{slug}/ssot/{f}")
        for sub in BUNDLE_DIRS:
            for f in sorted((d / sub).rglob("*")) if _plain(d, d / sub) else []:
                if f.is_file() and _plain(d, f):
                    z.write(f, f"{slug}/ssot/{f.relative_to(d)}")
        z.writestr(f"{slug}/README.txt", "Thư mục gốc: tài liệu đã build (Word, PowerPoint, Excel, Markdown).\n"
                   "ssot/: nguồn số liệu duy nhất — sửa assumptions.yaml rồi chạy `python gen.py build <slug>` "
                   "trong repo Gen-Planners để dựng lại toàn bộ.\n")
    return buf.getvalue()


def stage_progress(slug):
    p = load(project_dir(slug) / "project.yaml").get("stages") or {}
    return {"done": sum(1 for v in p.values() if v == "done"), "total": len(p)} if p else None
