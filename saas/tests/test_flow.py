"""Kiểm thử luồng đầy đủ không cần key AI: owner/user, phỏng vấn + brainstorm (demo), brief, job demo, hồ sơ, admin, phân quyền.

  GP_DATA=$(mktemp -d) python -m pytest saas/tests -q
"""
import os
import tempfile
import time

os.environ.setdefault("GP_DATA", tempfile.mkdtemp(prefix="gp-test-"))

from fastapi.testclient import TestClient  # noqa: E402

from saas.server import main  # noqa: E402

H = {"X-GP": "1"}


def client():
    return TestClient(main.app, headers=H)


def test_full_flow():
    with client() as owner, client() as user, client() as other:
        assert owner.post("/api/auth/signup", json={"email": "owner@x.io", "password": "password1"}).json()["role"] == "owner"
        assert user.post("/api/auth/signup", json={"email": "u@x.io", "password": "password1"}).json()["role"] == "user"
        other.post("/api/auth/signup", json={"email": "o@x.io", "password": "password1"})

        # CSRF: thiếu header → 403
        assert TestClient(main.app).post("/api/auth/login", json={}).status_code == 403
        # user thường không vào được admin
        assert user.get("/api/admin/overview").status_code == 403
        assert user.get("/api/admin/agents").status_code == 403

        p = user.post("/api/projects", json={"name": "Robot thú cưng", "idea": "Robot thú cưng AI có não tháo rời, câu lạc bộ, lớp huấn luyện."}).json()
        slug = p["slug"]
        assert other.get(f"/api/projects/{slug}").status_code == 403      # cô lập dữ liệu giữa user

        msgs = user.get(f"/api/projects/{slug}/messages?room=interview").json()
        assert msgs and msgs[0]["role"] == "assistant"
        r = user.post(f"/api/projects/{slug}/interview", json={"text": "Robot pet AI cho gia đình có con nhỏ"}).json()
        assert r["progress"]["answered"] == 1
        # sửa tay câu trả lời bắt buộc còn lại
        d = user.get(f"/api/projects/{slug}").json()
        req = {q["id"]: "trả lời mẫu" for q in d["questions"] if q.get("required")}
        assert user.put(f"/api/projects/{slug}/answers", json=req).json()["progress"]["required_missing"] == []

        b = user.post(f"/api/projects/{slug}/brainstorm", json={"text": "Mở góc trải nghiệm nhỏ trong trung tâm thương mại trước"}).json()
        assert len(b["proposals"]) == 1
        assert user.patch(f"/api/decisions/{b['proposals'][0]}", json={"status": "locked"}).json()["status"] == "locked"
        brief = user.post(f"/api/projects/{slug}/brief").json()["brief_md"]
        assert "Mở góc trải nghiệm" in brief and "Ý tưởng gốc" in brief

        # chạy bằng tài khoản hệ thống khi chưa có agent → 503
        assert user.post(f"/api/projects/{slug}/run", json={"billing": "owner"}).status_code == 503
        job = user.post(f"/api/projects/{slug}/run", json={"billing": "demo"}).json()["job_id"]
        for _ in range(240):
            j = user.get(f"/api/jobs/{job}").json()
            if j["status"] in ("done", "failed"):
                break
            time.sleep(0.5)
        assert j["status"] == "done", j["log"][-2000:]
        assert user.get(f"/api/projects/{slug}/export/project").status_code == 200
        assert user.get(f"/api/projects/{slug}/files/business-plan.md").status_code == 200
        v = user.get(f"/viewer/{slug}")
        assert v.status_code == 200 and "window.GP" in v.text

        # admin: agent profile, settings, users
        prof = owner.post("/api/admin/agents", json={"name": "agy chính", "engine": "agy"}).json()
        assert prof["is_active"] == 1
        owner.post(f"/api/admin/agents/{prof['id']}/check")
        assert owner.put("/api/admin/settings", json={"default_quota_jobs_month": "0"}).json()["default_quota_jobs_month"] == "0"
        assert user.post(f"/api/projects/{slug}/run", json={"billing": "owner"}).status_code == 403   # hết quota
        uid = next(u["id"] for u in owner.get("/api/admin/users").json() if u["email"] == "u@x.io")
        owner.patch(f"/api/admin/users/{uid}", json={"status": "disabled"})
        assert user.get("/api/me").status_code == 401                    # bị khoá → phiên mất hiệu lực
        assert owner.get("/api/admin/overview").json()["projects"] == 1
        assert any(a["action"] == "job_create" for a in owner.get("/api/admin/audit").json())
