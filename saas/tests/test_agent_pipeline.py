"""Đường ống core agent với CLI giả lập: stream-json → log + token + tiến độ stage, huỷ giữa chừng,
hết quota/chưa đăng nhập → tự chuyển tài khoản, máy chủ khởi động lại khi job đang chạy."""
import json
import os
import tempfile
import time
from pathlib import Path

os.environ.setdefault("GP_DATA", tempfile.mkdtemp(prefix="gp-test-"))

from fastapi.testclient import TestClient  # noqa: E402

from saas.server import agents, db, main, worker  # noqa: E402

FAKE = str(Path(__file__).parent / "fake" / "agent.py")
H = {"X-GP": "1"}


def wait(c, jid, until=("done", "failed", "cancelled"), t=60):
    for _ in range(t * 4):
        j = c.get(f"/api/jobs/{jid}").json()
        if j["status"] in until:
            return j
        time.sleep(0.25)
    raise AssertionError(f"job {jid} kẹt ở {j['status']}")


def test_agent_pipeline(monkeypatch):
    monkeypatch.setattr(worker, "which", lambda name: FAKE)          # mọi engine đều gọi CLI giả lập
    monkeypatch.setattr(agents, "which", lambda name: FAKE)
    with TestClient(main.app, headers=H) as o, TestClient(main.app, headers=H) as u:
        o.post("/api/auth/login", json={"email": "owner@x.io", "password": "password1"}).status_code == 200 or \
            o.post("/api/auth/signup", json={"email": "owner@x.io", "password": "password1"})
        o.put("/api/admin/settings", json={"allow_signup": "1", "default_quota_jobs_month": "10", "auto_failover": "1"})
        for prof in o.get("/api/admin/agents").json()["profiles"]:
            o.delete(f"/api/admin/agents/{prof['id']}")
        p1 = o.post("/api/admin/agents", json={"name": "Tài khoản 1", "engine": "claude", "priority": 1}).json()
        p2 = o.post("/api/admin/agents", json={"name": "Tài khoản 2", "engine": "claude", "priority": 2}).json()
        assert o.post(f"/api/admin/agents/{p1['id']}/check").json()["output"].startswith("9.9.9")
        o.post(f"/api/admin/agents/{p1['id']}/activate")
        u.post("/api/auth/signup", json={"email": "pipe@x.io", "password": "password1"}).status_code in (200, 409)
        u.post("/api/auth/login", json={"email": "pipe@x.io", "password": "password1"})
        slug = u.post("/api/projects", json={"name": "Pipeline", "idea": "Ý tưởng để test đường ống agent đầy đủ."}).json()["slug"]

        # 1. chạy thành công: log có sự kiện, token được cộng vào đúng profile, tiến độ 12/12, hồ sơ xuất ra
        os.environ["FAKE_AGENT_MODE"] = "ok"
        j = wait(u, u.post(f"/api/projects/{slug}/run", json={"billing": "owner", "force": True}).json()["job_id"])
        assert j["status"] == "done", j["log"][-1500:]
        assert "Đọc brief.md" in j["log"] and "⚙ Edit" in j["log"] and "✓ Đã xong" in j["log"]
        assert json.loads(j["usage"])["input_tokens"] == 12000
        assert db.one("SELECT SUM(input_tokens+output_tokens) t FROM usage WHERE profile_id=?", (p1["id"],))["t"] == 15400
        assert u.get(f"/api/projects/{slug}").json()["exported"]
        assert (main.WORKSPACE / slug / "brief.md").read_text().startswith("# Brief")
        assert u.get("/api/me").json()["quota"]["owner_jobs_month"] == 1

        # 2. hết quota trên cả 2 tài khoản: chuyển tài khoản 1 lần rồi dừng với thông báo rõ ràng
        os.environ["FAKE_AGENT_MODE"] = "quota"
        j = wait(u, u.post(f"/api/projects/{slug}/run", json={"billing": "owner", "force": True}).json()["job_id"])
        assert j["status"] == "failed" and j["attempt"] == 2 and "chuyển sang" in j["log"] and "hết quota" in j["error"]
        st = {p["id"]: p["status"] for p in o.get("/api/admin/agents").json()["profiles"]}
        assert st[p1["id"]] == st[p2["id"]] == "quota_exhausted"
        assert u.post(f"/api/projects/{slug}/run", json={"billing": "owner", "force": True}).status_code == 503   # không còn tài khoản

        # 3. chưa đăng nhập → đánh dấu cần đăng nhập
        for pid in (p1["id"], p2["id"]):
            o.patch(f"/api/admin/agents/{pid}", json={"reset_status": True})
        os.environ["FAKE_AGENT_MODE"] = "auth"
        o.patch(f"/api/admin/agents/{p2['id']}", json={"enabled": False})
        j = wait(u, u.post(f"/api/projects/{slug}/run", json={"billing": "owner", "force": True}).json()["job_id"])
        assert j["status"] == "failed" and "chưa đăng nhập" in j["error"]
        o.patch(f"/api/admin/agents/{p1['id']}", json={"reset_status": True})

        # 4. huỷ giữa chừng: tiến trình agent bị dừng thật, job = cancelled
        os.environ["FAKE_AGENT_MODE"] = "slow"
        jid = u.post(f"/api/projects/{slug}/run", json={"billing": "owner", "force": True}).json()["job_id"]
        wait(u, jid, until=("running",))
        for _ in range(40):
            if worker._running.get(jid):
                break
            time.sleep(0.25)
        proc = worker._running[jid]
        u.post(f"/api/jobs/{jid}/cancel")
        j = wait(u, jid)
        assert j["status"] == "cancelled" and proc.poll() is not None
        assert u.get(f"/api/projects/{slug}").json()["status"] != "running"
        # tính: lần thành công + lần huỷ SAU khi agent đã chạy (chống lách quota); không tính lỗi do tài khoản hệ thống
        assert u.get("/api/me").json()["quota"]["owner_jobs_month"] == 2

        # 5. máy chủ khởi động lại khi job đang chạy
        fake = db.insert("jobs", kind="plan", project_id=u.get(f"/api/projects/{slug}").json()["id"], user_id=1, engine="claude",
                         billing="owner", status="running", created=db.now())
        worker.recover()
        assert db.one("SELECT status, error FROM jobs WHERE id=?", (fake,))["status"] == "failed"
        os.environ.pop("FAKE_AGENT_MODE", None)
