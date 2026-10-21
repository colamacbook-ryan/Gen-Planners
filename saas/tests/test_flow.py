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
        r = owner.post("/api/auth/signup", json={"email": "owner@x.io", "password": "password1"})
        if r.status_code == 409:                                    # file test khác đã tạo owner trong cùng DB
            r = owner.post("/api/auth/login", json={"email": "owner@x.io", "password": "password1"})
        assert r.json()["role"] == "owner"
        owner.put("/api/admin/settings", json={"allow_signup": "1", "default_quota_jobs_month": "3"})
        assert user.post("/api/auth/signup", json={"email": "u@x.io", "password": "password1"}).json()["role"] == "user"
        other.post("/api/auth/signup", json={"email": "o@x.io", "password": "password1"})
        for prof in owner.get("/api/admin/agents").json()["profiles"]:   # bắt đầu khi chưa có core agent
            owner.delete(f"/api/admin/agents/{prof['id']}")

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
        assert owner.get("/api/admin/overview").json()["projects"] >= 1
        owner.patch(f"/api/admin/users/{uid}", json={"status": "active"})
        assert any(a["action"] == "job_create" for a in owner.get("/api/admin/audit").json())


def wait_job(c, jid, timeout=180):
    for _ in range(timeout * 2):
        j = c.get(f"/api/jobs/{jid}").json()
        if j["status"] in ("done", "failed", "cancelled"):
            return j
        time.sleep(0.5)
    raise AssertionError("job treo")


def test_growth_features():
    """Lời mời, dự án mẫu, onboarding, sửa số liệu + build lại, link chia sẻ, gói zip, chi tiết user."""
    with client() as owner, client() as user, client() as anon:
        if owner.post("/api/auth/login", json={"email": "owner@x.io", "password": "password1"}).status_code != 200:
            owner.post("/api/auth/signup", json={"email": "owner@x.io", "password": "password1"})   # chạy riêng test này
        owner.put("/api/admin/settings", json={"allow_signup": "0", "default_quota_jobs_month": "3"})
        assert user.post("/api/auth/signup", json={"email": "new@x.io", "password": "password1"}).status_code == 403
        inv = owner.post("/api/admin/invites", json={"email": "new@x.io", "quota_projects": 2, "days": 3}).json()
        assert anon.get(f"/api/public?invite={inv['token']}").json()["invite"]["email"] == "new@x.io"
        assert user.post("/api/auth/signup", json={"email": "other@x.io", "password": "password1", "invite": inv["token"]}).status_code == 400
        assert user.post("/api/auth/signup", json={"email": "new@x.io", "password": "password1", "invite": inv["token"]}).status_code == 200
        assert anon.post("/api/auth/signup", json={"email": "x@x.io", "password": "password1", "invite": inv["token"]}).status_code == 400  # dùng 1 lần
        me = user.get("/api/me").json()
        assert me["quota"]["projects_limit"] == 2 and me["onboarding"]["done"] == 0

        # dự án mẫu dùng chung: user đọc được, không ghi được
        if not owner.get("/api/samples").json():
            owner.post("/api/admin/seed-sample")
        for _ in range(120):
            sm = user.get("/api/samples").json()
            if sm and sm[0]["exported"] and sm[0]["status"] == "done":
                break
            time.sleep(0.5)
        slug_s = sm[0]["slug"]
        assert user.get(f"/api/projects/{slug_s}").status_code == 200
        assert user.post(f"/api/projects/{slug_s}/brief").status_code == 403
        user.post("/api/me/onboarding", json={"viewed_sample": True})

        # dự án riêng → demo build → sửa số liệu → build lại
        p = user.post("/api/projects", json={"name": "Tiệm bánh", "idea": "Tiệm bánh mì thủ công giao tận nhà trong khu căn hộ."}).json()
        slug = p["slug"]
        assert wait_job(user, user.post(f"/api/projects/{slug}/run", json={"billing": "demo", "force": True}).json()["job_id"])["status"] == "done"
        A = user.get(f"/api/projects/{slug}/assumptions").json()
        price = next(a for a in A["assumptions"] if a["id"] == "price_main")
        rev0 = A["kpi"]["revenue_last"]
        assert user.patch(f"/api/projects/{slug}/assumptions/price_main", json={"value": price["value"] * 2}).json()["value"] == price["value"] * 2
        assert user.patch(f"/api/projects/{slug}/assumptions/volume_main", json={"value": "1 2"}).status_code == 400   # sai số năm
        assert user.patch(f"/api/projects/{slug}/assumptions/price_main", json={"value": 3, "status": "verified"}).status_code == 400  # chưa có nguồn
        assert wait_job(user, user.post(f"/api/projects/{slug}/rebuild").json()["job_id"])["status"] == "done"
        d = user.get(f"/api/projects/{slug}").json()
        assert d["kpi"]["revenue_last"] > rev0 and d["changes"][0]["key"] == "price_main"
        assert "# SINGLE SOURCE OF TRUTH" in (main.WORKSPACE / slug / "assumptions.yaml").read_text()   # comment được giữ

        # lịch sử phiên bản: khởi tạo → chạy Plan → đổi giá; khôi phục dựng lại hồ sơ theo phiên bản cũ
        vs = user.get(f"/api/projects/{slug}/history").json()
        assert vs[0]["message"].startswith("Đổi Giá bán") and any(v["message"].startswith("Chạy Plan") for v in vs), vs
        assert "assumptions.yaml" in str(user.get(f"/api/projects/{slug}/history/{vs[0]['rev']}").json()["files"])
        plan_rev = next(v["rev"] for v in vs if v["message"].startswith("Chạy Plan"))
        r = user.post(f"/api/projects/{slug}/history/{plan_rev}/restore").json()
        assert wait_job(user, r["job_id"])["status"] == "done"
        assert user.get(f"/api/projects/{slug}").json()["kpi"]["revenue_last"] == rev0                # số quay về như trước khi sửa
        assert anon.get(f"/api/projects/{slug}/history").status_code == 401
        lint = user.get(f"/api/projects/{slug}/lint").json()
        assert lint["errors"] == [] and isinstance(lint["warnings"], list)
        # gói zip + link chia sẻ công khai
        z = user.get(f"/api/projects/{slug}/bundle.zip")
        assert z.status_code == 200 and z.content[:2] == b"PK"
        sh = user.post(f"/api/projects/{slug}/shares", json={"label": "Nhà đầu tư A"}).json()
        assert anon.get(sh["url"]).status_code == 200
        assert anon.get(f"/api/share/{sh['token']}/projects/{slug}/export/project").status_code == 200
        assert anon.get(f"/api/projects/{slug}/export/project").status_code == 401
        ob = user.get("/api/me").json()["onboarding"]
        assert {s["id"] for s in ob["steps"] if s["done"]} >= {"sample", "project", "plan", "share"}
        user.delete(f"/api/shares/{sh['id']}")
        assert anon.get(sh["url"]).status_code == 404
        assert not next(s for s in user.get("/api/me").json()["onboarding"]["steps"] if s["id"] == "share")["done"]   # link thu hồi không tính

        # owner xem chi tiết user + phễu
        uid = user.get("/api/me").json()["id"]
        det = owner.get(f"/api/admin/users/{uid}").json()
        assert det["projects"][0]["slug"] == slug and det["invited_by"]
        assert owner.get("/api/admin/overview").json()["funnel"]["plan"] >= 1
        assert "key_enc" not in owner.get("/api/admin/overview").text
        owner.put("/api/admin/settings", json={"allow_signup": "1"})
