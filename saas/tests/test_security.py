"""Hồi quy cho các lỗ đã tái hiện được: SSTI, thoát sandbox qua .git, symlink, XSS qua media, phạm vi API token, quyền job,
model làm sập build, body quá lớn. Mỗi test chạy đúng đường tấn công đã dùng để tái hiện."""
import io
import os
import tempfile
import time
import zipfile

os.environ.setdefault("GP_DATA", tempfile.mkdtemp(prefix="gp-test-"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from saas.server import history, main, sandbox, ssot  # noqa: E402
from saas.server.config import DATA, WORKSPACE  # noqa: E402

X = {"X-GP": "1"}


def login(c, email):
    if c.post("/api/auth/signup", json={"email": email, "password": "password1"}, headers=X).status_code != 200:
        assert c.post("/api/auth/login", json={"email": email, "password": "password1"}, headers=X).status_code == 200


def wait(c, jid):
    for _ in range(240):
        j = c.get(f"/api/jobs/{jid}").json()
        if j["status"] not in ("queued", "starting", "running"):
            return j
        time.sleep(0.25)
    raise AssertionError("job treo")


@pytest.fixture(scope="module")
def env():
    with TestClient(main.app, headers=X) as owner, TestClient(main.app, headers=X) as bob:
        login(owner, "sec-owner@x.io")
        main.db.x("UPDATE users SET role='owner' WHERE email='sec-owner@x.io'")   # các file test dùng chung DB: ai đăng ký đầu là owner
        login(bob, "sec-bob@x.io")
        slug = bob.post("/api/projects", json={"name": "Bảo mật", "idea": "Dự án thử các đường tấn công đã biết."}).json()["slug"]
        jid = bob.post(f"/api/projects/{slug}/run", json={"billing": "demo", "force": True}).json()["job_id"]
        assert wait(bob, jid)["status"] == "done"
        yield owner, bob, slug


def test_ssti_cannot_run_code(env):
    _, bob, slug = env
    payload = "{{ cycler.__init__.__globals__.os.popen('echo PWNED-$((6*7))').read() }}"
    assert bob.put(f"/api/projects/{slug}/ssot/sections/99-x.md", content=payload.encode()).status_code == 200
    out = bob.post(f"/api/projects/{slug}/check").json()["output"]
    assert "SecurityError" in out and "PWNED-42" not in out
    jid = bob.post(f"/api/projects/{slug}/rebuild").json()["job_id"]
    wait(bob, jid)
    plan = WORKSPACE / slug / "build" / "business-plan.md"
    assert not plan.exists() or "PWNED-42" not in plan.read_text()
    bob.put(f"/api/projects/{slug}/ssot/sections/99-x.md", content=b"# ok\n")


def test_git_config_in_project_cannot_run_commands(env, tmp_path):
    _, bob, slug = env
    marker = tmp_path / "fsmonitor-ran"
    d = WORKSPACE / slug
    assert not (d / ".git").exists() and history.git_dir(slug).exists()          # lịch sử nằm ngoài thư mục agent
    (d / ".git" / "hooks").mkdir(parents=True)                                     # agent cài .git giả với hook + fsmonitor
    (d / ".git" / "config").write_text(f"[core]\n\tfsmonitor = touch {marker}; false\n\thooksPath = .git/hooks\n")
    hook = d / ".git" / "hooks" / "pre-commit"
    hook.write_text(f"#!/bin/sh\ntouch {marker}\n")
    hook.chmod(0o755)
    (d / "research").mkdir(exist_ok=True)
    (d / "research" / "n.md").write_text("thay đổi để có commit\n")
    assert history.commit(slug, "thử")
    assert not marker.exists() and not (d / ".git").exists()


def test_symlinks_cannot_leak_or_write_outside(env, tmp_path):
    _, bob, slug = env
    d = WORKSPACE / slug
    secret = DATA / "session.key"
    (d / "sections" / "zz-leak.md").symlink_to(secret)
    (d / "media").mkdir(exist_ok=True)
    (d / "media" / "leak.png").symlink_to(secret)
    outside = tmp_path / "pwn.md"
    (d / "research").mkdir(exist_ok=True)
    (d / "research" / "x.md").symlink_to(outside)
    assert bob.get(f"/api/projects/{slug}/ssot/sections/zz-leak.md").status_code == 404
    assert bob.get(f"/api/projects/{slug}/media/leak.png").status_code == 404
    assert bob.put(f"/api/projects/{slug}/ssot/research/x.md", content=b"pwn").status_code == 400 and not outside.exists()
    z = zipfile.ZipFile(io.BytesIO(bob.get(f"/api/projects/{slug}/bundle.zip").content))
    assert not any("zz-leak" in n or "leak.png" in n for n in z.namelist())
    assert secret.read_bytes().strip().decode(errors="ignore") not in b"".join(z.read(n) for n in z.namelist()).decode(errors="ignore")
    gone = sandbox.strip_links(d)                                                   # sau mỗi lần agent chạy / trước build
    assert set(gone) >= {"sections/zz-leak.md", "media/leak.png", "research/x.md"}
    os.mkfifo(d / "research" / "fifo.md")
    assert sandbox.strip_links(d) == ["research/fifo.md"]


def test_media_only_serves_raster_images(env):
    owner, bob, slug = env
    d = WORKSPACE / slug / "media"
    d.mkdir(exist_ok=True)
    (d / "x.html").write_text("<script>alert(1)</script>")
    (d / "x.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>')
    (d / "ok.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    for n in ("x.html", "x.svg"):
        assert bob.get(f"/api/projects/{slug}/media/{n}").status_code == 404
    r = bob.get(f"/api/projects/{slug}/media/ok.png")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.headers["x-content-type-options"] == "nosniff"
    sandbox.strip_links(WORKSPACE / slug)
    assert wait(bob, bob.post(f"/api/projects/{slug}/rebuild").json()["job_id"])["status"] == "done"
    token = bob.post(f"/api/projects/{slug}/shares", json={}).json()["token"]
    with TestClient(main.app) as anon:
        assert anon.get(f"/api/share/{token}/projects/{slug}/media/x.svg").status_code == 404
        assert anon.get(f"/api/share/{token}/projects/{slug}/media/ok.png").status_code == 200


def test_api_token_is_scoped_to_agent_routes(env):
    owner, _, slug = env
    tok = owner.post("/api/tokens", json={"name": "agent"}).json()["token"]
    A = {"Authorization": f"Bearer {tok}"}
    with TestClient(main.app) as agent:
        for method, path in (("GET", "/api/admin/settings"), ("PUT", "/api/admin/settings"), ("POST", "/api/admin/users"),
                             ("GET", "/api/admin/agents"), ("GET", "/api/keys"), ("POST", "/api/keys"), ("GET", "/api/tokens"),
                             ("POST", "/api/me/password"), ("GET", "/api/admin/overview"), ("DELETE", f"/api/projects/{slug}")):
            assert agent.request(method, path, headers=A, json={}).status_code == 403, path
        assert agent.get("/api/samples", headers=A).status_code == 200
        assert agent.get("/api/standard/AGENTS.md", headers=A).status_code == 200


def test_admin_cannot_drive_someone_elses_job(env):
    owner, bob, slug = env
    jid = bob.post(f"/api/projects/{slug}/run", json={"billing": "external", "force": True}).json()["job_id"]
    for _ in range(40):
        if bob.get(f"/api/jobs/{jid}").json()["status"] == "waiting":
            break
        time.sleep(0.25)
    for path in ("handoff", "progress", "complete"):
        r = owner.request("GET" if path == "handoff" else "POST", f"/api/jobs/{jid}/{path}", json={})
        assert r.status_code == 404, path
    try:
        assert owner.get(f"/api/jobs/{jid}").status_code == 200                  # admin vẫn xem được
        assert owner.post(f"/api/jobs/{jid}/cancel").status_code == 200           # và huỷ được (vận hành)
    finally:
        bob.post(f"/api/jobs/{jid}/cancel")


def test_valuation_params_cannot_break_build(env):
    _, bob, slug = env
    for key, val in (("pre_money", 0), ("pre_money", -5), ("discount_rate", -1), ("raise_amount", -1)):
        r = bob.patch(f"/api/projects/{slug}/assumptions/{key}", json={"value": val})
        assert r.status_code == 400 and "phải" in r.json()["detail"], (key, val, r.text)


def test_oversized_bodies_rejected(env):
    _, bob, slug = env
    assert bob.post("/api/projects", content=b"{" + b" " * (1024 * 1024 + 10) + b"}",
                    headers={"content-type": "application/json"}).status_code == 413
    assert bob.put(f"/api/projects/{slug}/ssot/research/big.md", content=b"x" * (2 * 1024 * 1024 + 1)).status_code == 413


def test_concurrent_edits_do_not_lose_updates(env):
    import concurrent.futures as cf
    _, bob, slug = env
    keys = [r["id"] for r in bob.get(f"/api/projects/{slug}/assumptions").json()["assumptions"]
            if isinstance(r["value"], (int, float)) and not isinstance(r["value"], bool) and r["value"] > 1][:8]
    with cf.ThreadPoolExecutor(8) as ex:
        codes = list(ex.map(lambda k: bob.patch(f"/api/projects/{slug}/assumptions/{k}", json={"value": 7}).status_code, keys))
    assert codes == [200] * len(keys)
    vals = {r["id"]: r["value"] for r in ssot.read_assumptions(slug)["assumptions"]}
    assert all(vals[k] == 7 for k in keys)
