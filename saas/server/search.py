"""Tìm web + đọc trang cho engine native. Nhà cung cấp tìm kiếm do owner chọn (Cài đặt hệ thống → Chạy Plan):
Brave / Tavily (cần key, ổn định) hoặc DuckDuckGo (không cần key — dự phòng, có thể bị giới hạn).
Đọc trang chặn địa chỉ nội bộ ở mọi bước chuyển hướng (nội dung trang do bên thứ ba viết — có thể chứa chỉ dẫn độc hại).
"""
import html
import re
import urllib.parse

import httpx

from . import db
from .security import dec
from .ssot import _public

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36 GenPlanner",
      "Accept-Language": "vi,en;q=0.8"}
PROVIDERS = ("auto", "brave", "tavily", "duckduckgo", "none")
# Hướng dẫn lấy key tìm web (hiện ở Cài đặt hệ thống → Chạy Plan). Key Gemini miễn phí (AI Studio) không tìm web được:
# công cụ Google Search của Gemini bị từ chối (429) ở gói miễn phí.
GUIDES = {
    "tavily": {"tag": "Miễn phí 1.000 lượt/tháng · nên dùng", "url": "https://app.tavily.com/home", "url_label": "Mở Tavily (đăng ký / lấy key)",
               "steps": ["Đăng ký tại app.tavily.com (email, Google hoặc GitHub) — không cần thẻ.",
                         "Trang Overview hiện sẵn API key (bắt đầu bằng tvly-) → bấm copy.",
                         "Dán vào ô Key tìm web bên dưới, chọn loại Tavily, bấm Lưu cài đặt rồi Thử tìm web."],
               "cost": "Gói Researcher miễn phí 1.000 credit/tháng, reset đầu tháng; một lượt Plan dùng khoảng vài chục lượt tìm."},
    "brave": {"tag": "", "url": "https://api-dashboard.search.brave.com/app/keys", "url_label": "Mở Brave Search API dashboard",
              "steps": ["Đăng ký tại api-dashboard.search.brave.com.", "Chọn một gói Search (xem giá trên trang; có thể cần thẻ).",
                        "Vào API Keys → Add API key → copy.", "Dán vào ô Key tìm web bên dưới, chọn loại Brave, Lưu cài đặt rồi Thử tìm web."],
              "cost": "Xem bảng giá hiện hành trên trang Brave."},
}


class SearchError(Exception):
    pass


def provider():
    """Nhà cung cấp đang dùng. auto = Brave/Tavily nếu owner đã lưu key, không thì DuckDuckGo."""
    p = db.setting("search_provider") or "auto"
    if p == "auto":
        return (db.setting("search_key_kind") or "duckduckgo") if db.setting("search_key_enc") else "duckduckgo"
    return p


def search(query, n=8):
    """[{title, url, snippet}] — tối đa n kết quả."""
    p, key = provider(), dec(db.setting("search_key_enc")) if db.setting("search_key_enc") else ""
    q = str(query)[:300]
    try:
        if p == "brave":
            r = httpx.get("https://api.search.brave.com/res/v1/web/search", params={"q": q, "count": n},
                          headers={"X-Subscription-Token": key, "Accept": "application/json"}, timeout=25)
            r.raise_for_status()
            return [{"title": x.get("title", ""), "url": x.get("url", ""), "snippet": _text(x.get("description", ""))}
                    for x in (r.json().get("web") or {}).get("results", [])[:n]]
        if p == "tavily":
            r = httpx.post("https://api.tavily.com/search", json={"api_key": key, "query": q, "max_results": n}, timeout=30)
            r.raise_for_status()
            return [{"title": x.get("title", ""), "url": x.get("url", ""), "snippet": (x.get("content") or "")[:400]}
                    for x in r.json().get("results", [])[:n]]
        if p == "duckduckgo":
            r = httpx.post("https://html.duckduckgo.com/html/", data={"q": q}, headers=UA, timeout=25, follow_redirects=True)
            r.raise_for_status()
            if r.status_code == 202 or "anomaly" in r.text[:20000].lower():          # DuckDuckGo chặn máy chủ (IP datacenter) bằng captcha
                raise SearchError("DuckDuckGo chặn tìm kiếm từ máy chủ này. Owner nên thêm key Brave Search hoặc Tavily (đều có gói miễn phí) "
                                  "ở Cài đặt hệ thống → Chạy Plan. Tạm thời: dùng fetch_url với URL nguồn chính thức đã biết.")
            out = []
            for m in re.finditer(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?class="result__snippet"[^>]*>(.*?)</a>', r.text, re.S):
                url = m.group(1)
                if "uddg=" in url:                                   # link chuyển hướng của DuckDuckGo → URL gốc
                    url = urllib.parse.unquote(urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get("uddg", [url])[0])
                out.append({"title": _text(m.group(2)), "url": url, "snippet": _text(m.group(3))})
                if len(out) >= n:
                    break
            return out
    except httpx.HTTPError as e:
        raise SearchError(f"Tìm web lỗi ({p}): {type(e).__name__} {getattr(getattr(e, 'response', None), 'status_code', '')}".strip()) from e
    raise SearchError("Hệ thống chưa bật tìm web — dùng fetch_url với URL nguồn chính thức đã biết, hoặc ghi giả định là ước tính.")


def fetch(url, limit=12000):
    """Văn bản đọc được của một trang (bỏ script/style/thẻ), cắt ở `limit` ký tự."""
    for _ in range(5):
        if not _public(url):
            raise SearchError("Địa chỉ nội bộ — không được đọc")
        try:
            r = httpx.get(url, headers=UA, timeout=25, follow_redirects=False)
        except httpx.HTTPError as e:
            raise SearchError(f"Không mở được trang: {type(e).__name__}") from e
        if r.is_redirect and r.headers.get("location"):
            url = urllib.parse.urljoin(url, r.headers["location"])
            continue
        if r.status_code >= 400:
            raise SearchError(f"Trang trả HTTP {r.status_code}")
        ctype = r.headers.get("content-type", "")
        if "pdf" in ctype:
            return f"[PDF {len(r.content) // 1024} KB — không trích được chữ; dẫn URL làm nguồn và ghi số liệu theo trang/bảng cụ thể]"
        body = r.text[:600_000]
        title = _text((re.search(r"<title[^>]*>(.*?)</title>", body, re.S | re.I) or [None, ""])[1])
        text = _text(re.sub(r"<(script|style|noscript|svg|nav|footer|header)\b.*?</\1>", " ", body, flags=re.S | re.I))
        out = (f"# {title}\n{url}\n\n" if title else f"{url}\n\n") + text
        return out[:limit] + ("\n…[đã cắt]" if len(out) > limit else "")
    raise SearchError("Chuyển hướng quá nhiều")


def _text(s):
    s = re.sub(r"<br\s*/?>|</p>|</li>|</h\d>|</tr>", "\n", str(s), flags=re.I)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    return re.sub(r"[ \t\r\f\v]+", " ", re.sub(r"\n\s*\n+", "\n", s)).strip()
