#!/usr/bin/env python3
"""Dựng bản demo một-trang của Gen Planner SaaS để publish lên claude.ai (backend giả lập trong trình duyệt).

  python saas/demo/build.py <out_dir>

Ghép saas/static/{login,app,admin}.html thành index.html (mỗi trang là một <template> + một hàm khởi tạo),
nhúng mock.js (API giả lập, AI qua capability `sample`), tạo viewer.html từ studio/index.html, và chép dữ liệu
dự án mẫu (export JSON, media, file tải về). Chạy tools/export.py trước — xem saas/README.md.
"""
import base64
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "saas" / "static"
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "saas" / "demo" / "out")


def sub(s, old, new, count=1):
    assert old in s, f"không thấy: {old[:70]}"
    return s.replace(old, new, count)


def split_page(name):
    html = (STATIC / name).read_text()
    style = "\n".join(re.findall(r"<style>(.*?)</style>", html, re.S))
    body = re.search(r"<body>(.*?)<script src=\"/static/gp.js\"></script>", html, re.S).group(1)
    script = re.findall(r"<script>(.*?)</script>", html, re.S)[-1]
    return style, body, script


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    for c in OUT.iterdir():                     # xoá nội dung, giữ thư mục (để server xem thử không mất cwd)
        shutil.rmtree(c) if c.is_dir() else c.unlink()
    (OUT / "data" / "projects").mkdir(parents=True)
    pages = {n: split_page(n + ".html") for n in ("login", "app", "admin")}

    # --- điều hướng: thay URL máy chủ bằng điều hướng trong trang
    ls, lb, lj = pages["login"]
    lj = sub(lj, 'location.href = r.role === "owner" && mode === "signup" ? "/admin" : "/app";',
             'GPDEMO.nav(r.role === "owner" && mode === "signup" ? "admin" : "app");')
    lb = sub(lb, '<p class="hint" style="margin-top:16px" id="switch"></p>',
             '<p class="hint" style="margin-top:16px" id="switch"></p><p class="hint">Bản demo: tài khoản và dữ liệu chỉ lưu trong trình duyệt này.</p>')
    as_, ab, aj = pages["app"]
    ab = sub(ab, '<a href="/admin" id="navAdmin" hidden>', '<a href="#" onclick="GPDEMO.nav(\'admin\');return false" id="navAdmin" hidden>')
    aj = sub(aj, '<a href="/api/projects/${S.cur.slug}/brief.md"><button type="button">Tải brief.md</button></a>',
             '<button type="button" onclick="GPDEMO.saveBrief(\'${S.cur.slug}\')">Tải brief.md</button>')
    aj = sub(aj, '<a href="/viewer/${p.slug}" target="_blank" rel="noopener"><button type="button">Mở toàn màn hình ↗</button></a>',
             '<button type="button" onclick="document.querySelector(\'iframe.viewer\').requestFullscreen?.()">Toàn màn hình ⛶</button>')
    aj = sub(aj, 'src="/viewer/${p.slug}"', 'src="viewer.html#${encodeURIComponent(p.slug)}|${encodeURIComponent(p.name)}"')
    aj += "\nwindow.go = go;"
    ds, db, dj = pages["admin"]
    db = sub(db, '<a href="/app">← Về ứng dụng</a>', '<a href="#" onclick="GPDEMO.nav(\'app\');return false">← Về ứng dụng</a>')
    dj = sub(dj, '<a href="/viewer/${esc(p.slug)}" target="_blank" rel="noopener">Xem hồ sơ ↗</a>',
             '<a href="#" onclick="GPDEMO.nav(\'app\',\'p=${esc(p.slug)}&t=dossier\');return false">Xem hồ sơ</a>')
    dj = sub(dj, '<a href="/app#p=${esc(p.slug)}&t=interview">Mở</a>',
             '<a href="#" onclick="GPDEMO.nav(\'app\',\'p=${esc(p.slug)}&t=interview\');return false">Mở</a>')
    pages = {"login": (ls, lb, lj), "app": (as_, ab, aj), "admin": (ds, db, dj)}

    gp = (STATIC / "gp.js").read_text().replace('location.href = "/login"', 'GPDEMO.nav("login")')
    bank = yaml.safe_load((ROOT / "pipeline" / "interview.yaml").read_text())
    mock = (ROOT / "saas" / "demo" / "mock.js").read_text().replace("__BANK__", json.dumps(bank, ensure_ascii=False))
    css = (STATIC / "gp.css").read_text()

    shell = """
// Điều hướng giữa 3 trang trong một tài liệu: login · app · admin
(() => {
  const ids = new Set(), si = window.setInterval.bind(window), ci = window.clearInterval.bind(window);
  window.setInterval = (f, t, ...a) => { const id = si(f, t, ...a); ids.add(id); return id; };
  window.clearInterval = id => { ids.delete(id); ci(id); };
  const PAGES = {login: PAGE_login, app: PAGE_app, admin: PAGE_admin};
  GPDEMO.nav = (page, hash = "") => {
    ids.forEach(id => ci(id)); ids.clear(); window.onhashchange = null;
    try { sessionStorage.setItem("gp-page", page); } catch {}
    history.replaceState(null, "", location.pathname + location.search + (hash ? "#" + hash : ""));
    const root = document.getElementById("root");
    root.replaceChildren(document.getElementById("t-" + page).content.cloneNode(true));
    document.title = {login: "Gen Planner — Đăng nhập", app: "Gen Planner", admin: "Gen Planner — Quản trị"}[page];
    PAGES[page]();
  };
  let start = "login"; try { start = sessionStorage.getItem("gp-page") || "login"; } catch {}
  GPDEMO.nav(start, location.hash.slice(1));
})();
"""
    # index.html là nội dung trang: claude.ai tự bọc doctype/head/body khi publish
    head = """<title>Gen Planner</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,600&family=Public+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap">
<script src="https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/dompurify@3.1.6/dist/purify.min.js"></script>
<style>""" + css + "\n" + "\n".join(p[0] for p in pages.values()) + """
.demo-bar{position:fixed;right:12px;bottom:12px;z-index:30;display:flex;gap:8px;align-items:center;background:var(--hero);color:var(--hero-fg);border:1px solid var(--hero-line);border-radius:99px;padding:5px 6px 5px 12px;font-size:12px;box-shadow:0 4px 14px #0003}
@media (max-width:860px){.demo-bar span{display:none}.demo-bar{padding-left:6px}}
.demo-bar{right:max(12px,env(safe-area-inset-right,0px));bottom:calc(12px + env(safe-area-inset-bottom,0px))}
.demo-bar button{background:transparent;color:var(--hero-fg);border-color:var(--hero-line);border-radius:99px;padding:3px 10px;font-size:12px}
</style>
<div id="root"></div>
<div class="demo-bar" role="note"><span>Bản demo · dữ liệu trong trình duyệt · agent mô phỏng</span><button type="button" onclick="GPDEMO.reset()">Làm lại từ đầu</button></div>
"""
    tpl = "".join(f'<template id="t-{n}">{p[1]}</template>\n' for n, p in pages.items())
    fns = "".join(f"function PAGE_{n}() {{\n{p[2]}\n}}\n" for n, p in pages.items())
    html = head + tpl + "<script>\n" + mock + "\n</script>\n<script>\n" + gp + "\nwindow.toast = toast;\n" + fns + shell + "</script>\n"
    (OUT / "index.html").write_text(html)

    # --- trình xem hồ sơ
    v = (ROOT / "studio" / "index.html").read_text()
    v = sub(v, 'if(window.GP){location.href=`${window.GP.api}/projects/${id}/files/${f}`;m.textContent="Đang tải "+f;return}',
            'if(window.GP){parent.postMessage({gp:"download",project:window.GP_SLUG,file:f},"*");m.textContent="Đã gửi yêu cầu tải "+f+" — xác nhận ở hộp thoại.";return}')
    v = sub(v, 'if(!window.claude?.use&&window.GP){', 'if(window.GP){')   # trong iframe luôn đọc dữ liệu tĩnh của demo
    inject = """<script>
(() => { const [slug, name] = location.hash.slice(1).split("|").map(decodeURIComponent);
  const sample = slug === "ai-robot-pet-mau"; window.GP_SLUG = slug;
  window.GP = {api: "data", project: sample ? "ai-robot-pet" : "mau-template"};
  const f = window.fetch.bind(window);   // data/... → file .json tĩnh; dự án của người xem hiển thị khung template mang tên dự án
  window.fetch = async (u, o) => { u = String(u); if (u.startsWith("data/")) u += ".json"; const r = await f(u, o);
      if (sample || !u.endsWith("/export/project.json") || !r.ok) return r;
      const j = await r.json(); j.name = (name || j.name) + " (khung template — chưa nghiên cứu)"; return new Response(JSON.stringify(j)); };
})();
</script>
"""
    i = v.index("<script>")
    v = v[:i] + inject + v[i:]
    if not v.lstrip().lower().startswith("<!doctype"):   # file phụ được phục vụ nguyên trạng — cần khung HTML riêng
        v = ('<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
             '<title>Hồ sơ</title></head><body>' + v + "</body></html>")
    (OUT / "viewer.html").write_text(v)

    # --- dữ liệu: export JSON, media, file tải về
    tmp = Path(tempfile.mkdtemp())
    subprocess.run([sys.executable, str(ROOT / "tools/export.py"), "ai-robot-pet", "--out", str(tmp / "s"), "--media-base", "media"], check=True, capture_output=True)
    env = {"GP_PROJECTS": str(tmp / "ws"), "PATH": "/usr/bin:/bin:/usr/local/bin"}
    for cmd in (["new", "mau-template", "--name", "Dự án demo"], ["build", "mau-template"]):
        subprocess.run([sys.executable, str(ROOT / "gen.py"), *cmd], check=True, capture_output=True, env=env)
    subprocess.run([sys.executable, str(ROOT / "tools/export.py"), "mau-template", "--out", str(tmp / "t"), "--media-base", "media"], check=True, capture_output=True, env=env)
    for pid, src in (("ai-robot-pet", tmp / "s"), ("mau-template", tmp / "t")):
        d = OUT / "data" / "projects" / pid / "export"
        d.mkdir(parents=True)
        for part in ("project", "dossier", "documents"):
            shutil.copy(src / f"{part}.json", d / f"{part}.json")
    shutil.copytree(ROOT / "projects" / "ai-robot-pet" / "media", OUT / "media")
    (OUT / "files").mkdir()
    b = ROOT / "projects" / "ai-robot-pet" / "build"
    for f in ("business-plan.docx", "deck.pptx", "financials.xlsx"):
        (OUT / "files" / f"{f}.b64.txt").write_text(base64.b64encode((b / f).read_bytes()).decode())
    shutil.copy(b / "business-plan.md", OUT / "files" / "business-plan.md.txt")
    shutil.rmtree(tmp)
    print(f"✓ demo → {OUT}  ({sum(1 for _ in OUT.rglob('*') if _.is_file())} file)")


if __name__ == "__main__":
    build()
