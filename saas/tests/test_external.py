"""Agent ngoài làm việc qua API token: nhận việc, đọc chuẩn, ghi SSOT, check, nộp bài."""
import os
import tempfile
import time

os.environ.setdefault("GP_DATA", tempfile.mkdtemp(prefix="gp-test-"))

from fastapi.testclient import TestClient  # noqa: E402

from saas.server import main  # noqa: E402


def test_external_agent_flow():
    with TestClient(main.app, headers={"X-GP": "1"}) as web, TestClient(main.app) as agent, TestClient(main.app) as intruder:
        if web.post("/api/auth/signup", json={"email": "ext@x.io", "password": "password1"}).status_code != 200:
            web.post("/api/auth/login", json={"email": "ext@x.io", "password": "password1"})
        slug = web.post("/api/projects", json={"name": "Agent ngoài", "idea": "Dự án để test agent ngoài làm việc qua API."}).json()["slug"]
        tok = web.post("/api/tokens", json={"name": "Claude Code"}).json()["token"]
        A = {"Authorization": f"Bearer {tok}"}
        assert agent.post("/api/tokens", headers=A, json={}).status_code == 403          # token không tự đẻ token
        assert agent.put(f"/api/projects/{slug}/ssot/idea.md", headers=A, content=b"x").status_code == 404   # chưa có workspace
        jid = web.post(f"/api/projects/{slug}/run", json={"billing": "external", "force": True}).json()["job_id"]
        for _ in range(40):
            if web.get(f"/api/jobs/{jid}").json()["status"] == "waiting":
                break
            time.sleep(0.25)
        h = agent.get(f"/api/jobs/{jid}/handoff", headers=A).json()
        assert slug in h["prompt"] and "AGENTS.md" in h["standard"]
        assert "founder-first" in agent.get("/api/standard/pipeline/playbook.yaml", headers=A).text
        assert agent.get("/api/standard/saas/data/app.db", headers=A).status_code == 404
        files = {f["path"] for f in agent.get(f"/api/projects/{slug}/ssot", headers=A).json()}
        assert {"idea.md", "brief.md", "assumptions.yaml"} <= files
        # ghi hợp lệ / bị chặn
        assert agent.put(f"/api/projects/{slug}/ssot/research/01-global-market.md", headers=A, content="# R1\n".encode()).status_code == 200
        for bad in ("../../app.db", "brief.md", "sections/../x.md", "build/deck.pptx", "media/x.exe", ".hidden.md"):
            assert agent.put(f"/api/projects/{slug}/ssot/{bad}", headers=A, content=b"x").status_code in (400, 404, 405), bad
        assert agent.put(f"/api/projects/{slug}/ssot/assumptions.yaml", headers=A, content=b"a: [1, 2").status_code == 400
        assert agent.put(f"/api/projects/{slug}/ssot/media/big.jpg", headers=A, content=b"0" * (2 * 1024 * 1024 + 1)).status_code == 413
        # tiến độ stage hiện cho founder
        py = agent.get(f"/api/projects/{slug}/ssot/project.yaml", headers=A).text.replace("01-intake: todo", "01-intake: done")
        agent.put(f"/api/projects/{slug}/ssot/project.yaml", headers=A, content=py.encode())
        assert '"done": 1' in web.get(f"/api/jobs/{jid}").json()["progress"]
        agent.post(f"/api/jobs/{jid}/progress", headers=A, json={"message": "Xong R1"})
        chk = agent.post(f"/api/projects/{slug}/check", headers=A).json()
        assert "errors" in chk and str(main.WORKSPACE) not in chk["output"]               # không lộ đường dẫn máy chủ
        # người khác: không đọc/ghi được, kể cả có token của chính họ
        if intruder.post("/api/auth/signup", json={"email": "intr@x.io", "password": "password1"}, headers={"X-GP": "1"}).status_code != 200:
            intruder.post("/api/auth/login", json={"email": "intr@x.io", "password": "password1"}, headers={"X-GP": "1"})
        t2 = intruder.post("/api/tokens", json={}, headers={"X-GP": "1"}).json()["token"]
        B = {"Authorization": f"Bearer {t2}"}
        assert intruder.get(f"/api/projects/{slug}/ssot/idea.md", headers=B).status_code == 403
        assert intruder.post(f"/api/jobs/{jid}/complete", headers=B, json={}).status_code == 404
        # nộp bài → build + export → done
        assert agent.post(f"/api/jobs/{jid}/complete", headers=A, json={"summary": "Đã nghiên cứu R1"}).json()["ok"]
        for _ in range(120):
            j = web.get(f"/api/jobs/{jid}").json()
            if j["status"] in ("done", "failed"):
                break
            time.sleep(0.5)
        assert j["status"] == "done" and "Agent nộp bài" in j["log"], j["log"][-800:]
        assert web.get(f"/api/projects/{slug}").json()["exported"]
        # sửa sau khi nộp: ngày tháng YAML không ngoặc kép (lỗi agent thật gặp) vẫn xuất được; build lại cập nhật hồ sơ
        ev = agent.get(f"/api/projects/{slug}/ssot/evidence.yaml", headers=A).text
        ev += "\n  ev-test: {title: Nguồn thử, publisher: Thử nghiệm, date: 2026-03-19, url: 'https://example.org', type: web}\n" if "ev-" in ev else ""
        if ev:
            assert agent.put(f"/api/projects/{slug}/ssot/evidence.yaml", headers=A, content=ev.encode()).status_code == 200
        chk = agent.post(f"/api/projects/{slug}/check", headers=A).json()
        assert chk["errors"] == 0, chk["output"][-1500:]
        assert agent.get(f"/api/projects/{slug}/files/deck.md", headers=A).status_code == 200
        rj = agent.post(f"/api/projects/{slug}/rebuild", headers=A).json()["job_id"]
        for _ in range(120):
            if web.get(f"/api/jobs/{rj}").json()["status"] in ("done", "failed"):
                break
            time.sleep(0.5)
        assert web.get(f"/api/jobs/{rj}").json()["status"] == "done"
        log = web.get(f"/api/jobs/{rj}").json()["log"]
        assert str(main.WORKSPACE) not in log and "/home/" not in log                    # log không lộ đường dẫn máy chủ
        # thu hồi token → mất quyền ngay
        tid = web.get("/api/tokens").json()[0]["id"]
        web.delete(f"/api/tokens/{tid}")
        assert agent.get(f"/api/projects/{slug}/ssot", headers=A).status_code == 401
