"""Các lỗi trải nghiệm người mới mà QA đã gặp: key sai vẫn lưu, onboarding kẹt khi chỉ có demo, câu hỏi bị biến thành điểm chốt,
tên dự án chứa HTML, link chia sẻ không tên, trang chia sẻ không có viewport."""
import os
import tempfile

os.environ.setdefault("GP_DATA", tempfile.mkdtemp(prefix="gp-test-"))

from fastapi.testclient import TestClient  # noqa: E402

from saas.server import db, main  # noqa: E402

X = {"X-GP": "1"}


def user(c, email):
    if c.post("/api/auth/signup", json={"email": email, "password": "password1"}, headers=X).status_code != 200:
        c.post("/api/auth/login", json={"email": email, "password": "password1"}, headers=X)


def test_new_user_rough_edges():
    db.set_setting("allow_demo_engine", "1")
    with TestClient(main.app, headers=X) as c:
        user(c, "ux@x.io")
        me = c.get("/api/me").json()
        key = next(s for s in me["onboarding"]["steps"] if s["id"] == "key")
        assert key["optional"] and me["onboarding"]["total"] == 6          # chỉ có demo: bước key không chặn tiến độ
        assert "core_ready" in me
        r = c.post("/api/keys", json={"provider": "anthropic", "key": "sk-ant-invalid-0000000000"})
        assert r.status_code == 400 and "từ chối" in r.json()["detail"]
        assert c.get("/api/keys").json() == []                               # key sai không được lưu, không thành mặc định

        p = c.post("/api/projects", json={"name": 'Quán phở <img src=x onerror=alert(1)>', "idea": "Quán phở có robot pha chế cho khách."}).json()
        slug = p["slug"]
        msgs = c.get(f"/api/projects/{slug}/messages?room=interview").json()
        assert msgs and "<img" not in msgs[0]["content"] and "&lt;img" in msgs[0]["content"]
        brief = c.post(f"/api/projects/{slug}/brief").json()["brief_md"]
        assert "<img" not in brief.splitlines()[0]

        c.post(f"/api/projects/{slug}/brainstorm", json={"text": "Mảng nào nên làm trước để có dòng tiền?"})
        assert not [d for d in c.get(f"/api/projects/{slug}").json()["decisions"] if "Mảng nào" in d["title"]]
        c.post(f"/api/projects/{slug}/brainstorm", json={"text": "Làm mảng đồ uống trước để có dòng tiền sớm."})
        assert [d for d in c.get(f"/api/projects/{slug}").json()["decisions"] if "đồ uống" in d["title"]]


def test_share_page_is_mobile_ready_and_links_get_a_label():
    html = (main.ROOT / "studio" / "index.html").read_text()
    assert html.lower().startswith("<!doctype html>") and 'name="viewport"' in html[:400]


def test_page_scripts_parse(tmp_path):
    """Script nhúng trong các trang phải parse được — một dấu // lạc từng làm hỏng cả trang đăng nhập."""
    import re
    import shutil
    import subprocess
    import pytest
    node = shutil.which("node")
    if not node:
        pytest.skip("không có node")
    for name in ("login.html", "app.html", "admin.html", "gp.js"):
        src = (main.SAAS / "static" / name).read_text()
        js = src if name.endswith(".js") else "\n".join(re.findall(r"<script>(.*?)</script>", src, re.S))
        f = tmp_path / (name + ".js")
        f.write_text(js)
        r = subprocess.run([node, "--check", str(f)], capture_output=True, text=True)
        assert r.returncode == 0, f"{name}: {r.stderr[:400]}"
    studio = (main.ROOT / "studio" / "index.html").read_text()
    f = tmp_path / "studio.js"
    f.write_text("\n".join(re.findall(r"<script>(.*?)</script>", studio, re.S)))
    assert subprocess.run([node, "--check", str(f)], capture_output=True).returncode == 0
