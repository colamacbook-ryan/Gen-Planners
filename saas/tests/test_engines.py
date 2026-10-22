"""Chạy Plan bằng API key: key của người dùng → engine native (gọi thẳng API, function calling), không dùng CLI.
CLI agy / Claude Code chỉ là tài khoản gói tháng của owner. Kiểm: định tuyến, vòng tool-call end-to-end với LLM giả lập,
trần chi phí, công cụ chỉ chạm SSOT của đúng dự án, đọc trang chặn địa chỉ nội bộ, lỗi được giải thích rõ."""
import json
import os
import tempfile
import time
from pathlib import Path

os.environ.setdefault("GP_DATA", tempfile.mkdtemp(prefix="gp-test-"))

import httpx  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from saas.server import agents, db, llm, main, native, sandbox, search, worker  # noqa: E402
from saas.server.config import WORKSPACE  # noqa: E402

X = {"X-GP": "1"}


def login(c, email, role=None):
    if c.post("/api/auth/signup", json={"email": email, "password": "password1"}).status_code != 200:
        c.post("/api/auth/login", json={"email": email, "password": "password1"})
    if role:
        db.x("UPDATE users SET role=? WHERE email=?", (role, email))


def wait(c, jid, t=180):
    for _ in range(t * 4):
        j = c.get(f"/api/jobs/{jid}").json()
        if j["status"] in ("done", "failed", "cancelled"):
            return j
        time.sleep(0.25)
    raise AssertionError(f"job {jid} kẹt ở {j['status']}")


def call(name, **args):
    return {"id": f"c-{name}-{time.monotonic_ns()}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


def scripted(cost=0.001, seen=None):
    """LLM giả lập: mỗi stage tìm web → ghi research → (stage cuối: run_check) → finish_stage."""
    def fake(provider, key, model, messages, tools, max_tokens=4096, retries=4):
        if seen is not None:
            seen.append((provider, key, model, messages))
        sid = messages[1]["content"].split()[1]
        step = sum(m["role"] == "assistant" for m in messages)
        plan = [call("web_search", query=f"thị trường {sid}"),
                call("write_file", path=f"research/{sid}.md", content=f"# {sid}\n\nNguồn: https://example.org/a\n"),
                *([call("run_check")] if sid == native.CONSOLE_STAGE["id"] else []),
                call("finish_stage", summary=f"xong {sid}", done=True)]
        return ({"role": "assistant", "content": f"bước {step}", "tool_calls": [plan[min(step, len(plan) - 1)]]},
                {"input_tokens": 1000, "cached_tokens": 200, "output_tokens": 100, "cost_usd": cost})
    return fake


@pytest.fixture
def offline_search(monkeypatch):
    monkeypatch.setattr(search, "search", lambda q, n=8: [{"title": "Kết quả", "url": "https://example.org/a", "snippet": q}])
    monkeypatch.setattr(search, "fetch", lambda url, limit=12000: f"# Trang\n{url}\n\nnội dung")


def test_user_key_runs_native_end_to_end(monkeypatch, offline_search):
    seen = []
    monkeypatch.setattr(llm, "chat_tools", scripted(seen=seen))
    with TestClient(main.app, headers=X) as u:
        login(u, "native@x.io")
        db.set_setting("plan_billing", "either")
        k = u.post("/api/keys", json={"provider": "deepseek", "key": "sk-deepseek-test-000000"}).json()
        assert k["plan_engine"] == "native"
        slug = u.post("/api/projects", json={"name": "Native", "idea": "Dự án thử engine native chạy bằng key DeepSeek."}).json()["slug"]
        r = u.post(f"/api/projects/{slug}/run", json={"billing": "user_key", "api_key_id": k["id"], "force": True})
        assert r.status_code == 200, r.text
        j = wait(u, r.json()["job_id"])
        assert j["status"] == "done", j["log"][-2000:]
        assert j["engine"] == "native" and j["model"] == "deepseek-flash"                 # model mặc định rẻ của DeepSeek
        assert {s[:3] for s in seen} == {("deepseek", "sk-deepseek-test-000000", "deepseek-flash")}
        d = WORKSPACE / slug
        total = json.loads(j["progress"])["total"]
        assert (d / "research" / "13-console.md").exists() and len(list((d / "research").glob("*.md"))) >= total
        py = (d / "project.yaml").read_text()
        assert "13-console: done" in py
        assert "Engine native · deepseek · model deepseek-flash" in j["log"] and "Số lỗi" not in j["log"]
        usage = json.loads(j["usage"])
        assert usage["calls"] > 13 * 3 and usage["cost_usd"] == pytest.approx(usage["calls"] * 0.001, rel=1e-3)
        row = db.one("SELECT * FROM usage WHERE project_id=(SELECT id FROM projects WHERE slug=?) AND source='job'", (slug,))
        assert row["provider"] == "user:deepseek" and row["model"] == "deepseek-flash"
        assert json.loads(j["progress"])["done"] == total


def test_budget_stop_keeps_finished_stages(monkeypatch, offline_search):
    monkeypatch.setattr(llm, "chat_tools", scripted(cost=0.05))
    with TestClient(main.app, headers=X) as u:
        login(u, "native-budget@x.io")
        db.set_setting("plan_billing", "either")
        k = u.post("/api/keys", json={"provider": "deepseek", "key": "sk-deepseek-test-000001"}).json()
        slug = u.post("/api/projects", json={"name": "Budget", "idea": "Dự án thử trần chi phí của engine native."}).json()["slug"]
        jid = u.post(f"/api/projects/{slug}/run", json={"billing": "user_key", "api_key_id": k["id"], "budget_usd": "0,5", "force": True}).json()["job_id"]
        j = wait(u, jid)
        assert j["status"] == "failed" and "Đã chạm trần" in j["error"] and "chạy tiếp từ stage dở" in j["error"], j["error"]
        assert json.loads(j["usage"])["cost_usd"] == pytest.approx(0.5, abs=0.06)
        done = (WORKSPACE / slug / "project.yaml").read_text().count(": done")
        total = len(native.Run({"id": jid}, {"slug": slug}, "deepseek", "k", "m", None, None).stages()[0]) + done
        assert 1 <= done < total                                                # phần đã làm vẫn còn
        assert "Build phần đã làm" in j["log"]
        # chạy lại: bỏ qua stage đã xong
        monkeypatch.setattr(llm, "chat_tools", scripted(cost=0.0))
        j2 = wait(u, u.post(f"/api/projects/{slug}/run", json={"billing": "user_key", "api_key_id": k["id"], "force": True}).json()["job_id"])
        assert j2["status"] == "done" and f"{total - done}/{total} stage cần làm" in j2["log"]


def test_native_tools_only_touch_project_ssot(tmp_path):
    p = {"slug": "tools-proj", "country": "Việt Nam"}
    d = WORKSPACE / p["slug"]
    (d / "sections").mkdir(parents=True, exist_ok=True)
    (d / "brief.md").write_text("brief")
    (d / "assumptions.yaml").write_text("a: 1\n")
    logs = []
    r = native.Run({"id": 0, "budget_usd": 1}, p, "deepseek", "k", "deepseek-flash", logs.append, lambda s: {"errors": 0, "output": ""})
    assert "không thuộc bộ SSOT" in r.tool("write_file", {"path": "../evil.md", "content": "x"})
    assert "không thuộc bộ SSOT" in r.tool("write_file", {"path": "build/x.html", "content": "x"})
    assert "không thuộc bộ SSOT" in r.tool("read_file", {"path": "/etc/passwd"})
    assert "chỉ đọc" in r.tool("write_file", {"path": "brief.md", "content": "đổi brief"})
    assert "Lỗi YAML" in r.tool("write_file", {"path": "evidence.yaml", "content": "a: [1, 2"})
    assert "quá lớn" in r.tool("write_file", {"path": "sections/01.md", "content": "x" * 400_001})
    assert r.tool("write_file", {"path": "sections/01-tong-quan.md", "content": "Mở đầu. Mở đầu."}) == "Đã ghi sections/01-tong-quan.md."
    assert "xuất hiện 2 lần" in r.tool("edit_file", {"path": "sections/01-tong-quan.md", "old": "Mở đầu.", "new": "A"})
    assert r.tool("edit_file", {"path": "sections/01-tong-quan.md", "old": "Mở đầu. Mở", "new": "Bắt đầu. Mở"}).startswith("Đã ghi")
    assert "brief" == r.tool("read_file", {"path": "brief.md"})
    r.allowed = {"sections/02-market.md", "evidence.yaml", "assumptions.yaml"}                # luật: stage chỉ ghi file của nó
    assert "chỉ được ghi" in r.tool("write_file", {"path": "deck.md", "content": "x"})
    assert r.tool("write_file", {"path": "research/r2-thi-truong.md", "content": "x"}).startswith("Đã ghi")
    r.allowed = None
    # chống bịa nguồn: URL chưa thấy qua web_search / fetch_url bị từ chối
    assert "chưa từng xuất hiện" in r.tool("write_file", {"path": "research/r1.md", "content": "Số liệu theo https://gso.gov.vn/bao-cao-2025"})
    r.seen.add(native._norm("https://gso.gov.vn/bao-cao-2025/"))
    assert r.tool("write_file", {"path": "research/r1.md", "content": "Số liệu theo https://gso.gov.vn/bao-cao-2025."}).startswith("Đã ghi")
    assert r.tool("edit_file", {"path": "research/r1.md", "old": "Số liệu", "new": "Dữ liệu"}).startswith("Đã ghi")   # URL cũ không bị chặn lại
    # ghi đè làm mất nội dung stage trước
    (d / "evidence.yaml").write_text("ev-001:\n  title: nguồn cũ\n" * 120)
    assert "sẽ mất nội dung" in r.tool("write_file", {"path": "evidence.yaml", "content": "ev-002:\n  title: mới\n"})
    assert "Không có file chuẩn" in r.tool("read_standard", {"name": "saas/server/security.py"})
    assert "plan-as-code" in r.tool("read_standard", {"name": "CLAUDE.md"})
    link = d / "sections" / "link.md"
    link.symlink_to("/etc/hostname")
    assert "Lỗi" in r.tool("write_file", {"path": "sections/link.md", "content": "x"}) and Path("/etc/hostname").read_text() != "x"


def test_guard_stops_on_cancel_budget_tokens():
    with TestClient(main.app, headers=X):
        jid = db.insert("jobs", kind="plan", status="running", engine="native", billing="user_key", created=db.now())
        r = native.Run({"id": jid, "budget_usd": 1}, {"slug": "g"}, "deepseek", "k", "m", lambda t: None, None)
        r.usage["cost_usd"] = 1.0
        with pytest.raises(native.Stop, match="budget"):
            r.guard()
        r.usage["cost_usd"], r.cost_known = 99, False                    # model không có giá → vẫn chặn theo token
        r.usage["input_tokens"] = r.token_cap
        with pytest.raises(native.Stop, match="token"):
            r.guard()
        db.update("jobs", jid, status="cancelled")
        with pytest.raises(native.Stop, match="cancelled"):
            r.guard()


def test_chat_tools_usage_cost_and_retry(monkeypatch):
    sent, replies = [], []

    def fake_post(url, **kw):
        sent.append((url, kw))
        return replies.pop(0)
    monkeypatch.setattr(llm.httpx, "post", fake_post)
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    ok = {"choices": [{"message": {"role": "assistant", "content": "", "tool_calls": []}}],
          "usage": {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000, "prompt_cache_hit_tokens": 500_000}}
    replies[:] = [httpx.Response(429, json={"error": {"message": "rate limited"}}), httpx.Response(200, json=ok)]
    msg, u = llm.chat_tools("deepseek", "k", "deepseek-flash", [{"role": "user", "content": "hi"}], native.TOOLS)
    assert len(sent) == 2 and sent[0][0] == "https://api.deepseek.com/chat/completions"
    assert sent[0][1]["headers"]["Authorization"] == "Bearer k" and sent[0][1]["json"]["tools"] == native.TOOLS
    assert u["cached_tokens"] == 500_000 and u["cost_usd"] == pytest.approx(0.5 * 0.30 + 0.5 * 0.006 + 1.20)
    replies[:] = [httpx.Response(200, json={**ok, "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.0123}})]
    _, u = llm.chat_tools("openrouter", "k", "deepseek/deepseek-v4-flash", [], native.TOOLS)
    assert sent[-1][1]["json"]["usage"] == {"include": True} and u["cost_usd"] == 0.0123
    replies[:] = [httpx.Response(200, json={**ok, "usage": {"prompt_tokens": 10, "completion_tokens": 5}})]
    assert llm.chat_tools("openai", "k", "gpt-x", [], native.TOOLS)[1]["cost_usd"] is None   # không biết giá → chặn bằng trần token
    replies[:] = [httpx.Response(401, json={"error": {"message": "invalid key"}})]
    with pytest.raises(llm.LLMError, match="401"):
        llm.chat_tools("deepseek", "bad", "deepseek-flash", [], native.TOOLS)


def test_run_route_validation():
    with TestClient(main.app, headers=X) as u:
        login(u, "native-route@x.io")
        db.set_setting("plan_billing", "either")
        k = u.post("/api/keys", json={"provider": "openrouter", "key": "sk-or-v1-testkey-000000", "model": "openai/gpt-x"}).json()
        db.update("api_keys", k["id"], model="")                               # key cũ không có model
        slug = u.post("/api/projects", json={"name": "Route", "idea": "Dự án thử kiểm tra tham số chạy Plan bằng key."}).json()["slug"]
        r = u.post(f"/api/projects/{slug}/run", json={"billing": "user_key", "api_key_id": k["id"], "force": True})
        assert r.status_code == 200 and db.one("SELECT model FROM jobs WHERE id=?", (r.json()["job_id"],))["model"] == "deepseek/deepseek-v4.1-flash"
        u.post(f"/api/jobs/{r.json()['job_id']}/cancel")
        ko = u.post("/api/keys", json={"provider": "openai", "key": "sk-openai-test-000000", "model": "gpt-x"}).json()
        db.update("api_keys", ko["id"], model="")                              # OpenAI không có model mặc định → phải chọn
        r = u.post(f"/api/projects/{slug}/run", json={"billing": "user_key", "api_key_id": ko["id"], "force": True})
        assert r.status_code == 400 and "Chọn model" in r.json()["detail"]
        for bad in ("abc", "0", "5000"):
            r = u.post(f"/api/projects/{slug}/run", json={"billing": "user_key", "api_key_id": k["id"], "model": "x/y", "budget_usd": bad, "force": True})
            assert r.status_code == 400, bad
        r = u.post(f"/api/projects/{slug}/run", json={"billing": "user_key", "api_key_id": k["id"], "model": "deepseek/deepseek-v4-flash",
                                                       "budget_usd": "2,5", "force": True})
        assert r.status_code == 200
        j = db.one("SELECT * FROM jobs WHERE id=?", (r.json()["job_id"],))
        assert (j["engine"], j["model"], j["budget_usd"]) == ("native", "deepseek/deepseek-v4-flash", 2.5)
        u.post(f"/api/jobs/{j['id']}/cancel")


def test_owner_native_profile_and_cli_is_subscription_only(monkeypatch):
    monkeypatch.setattr(llm, "list_models", lambda p, k: ["deepseek-flash", "deepseek-v4-pro"])
    with TestClient(main.app, headers=X) as o:
        login(o, "owner-native@x.io", "owner")
        r = o.post("/api/admin/agents", json={"name": "CLI key", "engine": "claude", "auth_mode": "api_key", "key": "sk-ant-x"})
        assert r.status_code == 400 and "gói tháng" in r.json()["detail"]
        assert o.post("/api/admin/agents", json={"name": "Thiếu key", "engine": "native", "provider": "deepseek"}).status_code == 400
        p = o.post("/api/admin/agents", json={"name": "DeepSeek hệ thống", "engine": "native", "provider": "deepseek",
                                              "key": "sk-ds-owner-000000", "priority": 0}).json()
        assert p["provider"] == "deepseek" and p["installed"] and "key_enc" not in p
        assert o.post(f"/api/admin/agents/{p['id']}/check").json()["ok"]
        assert o.post(f"/api/admin/agents/{p['id']}/models").json()["models"] == ["deepseek-flash", "deepseek-v4-pro"]
        o.post(f"/api/admin/agents/{p['id']}/activate")
        o.put("/api/admin/settings", json={"owner_job_budget_usd": "1.5", "plan_billing": "either"})
        slug = o.post("/api/projects", json={"name": "Owner native", "idea": "Dự án thử profile Engine API của hệ thống."}).json()["slug"]
        jid = o.post(f"/api/projects/{slug}/run", json={"billing": "owner", "force": True}).json()["job_id"]
        j = db.one("SELECT * FROM jobs WHERE id=?", (jid,))
        assert (j["engine"], j["budget_usd"]) == ("native", 1.5)
        o.post(f"/api/jobs/{jid}/cancel")
        assert "providers" in o.get("/api/admin/agents").json()
        o.delete(f"/api/admin/agents/{p['id']}")


def test_every_provider_has_a_key_guide():
    with TestClient(main.app, headers=X) as u:
        login(u, "guide@x.io")
        ps = u.get("/api/providers").json()
        for k, p in ps.items():
            g = p["guide"]
            assert g and g["url"].startswith("https://") and len(g["steps"]) >= 3 and g["url_label"], k
        assert "miễn phí" in ps["gemini"]["guide"]["tag"].lower() and "KHÔNG đủ" in ps["gemini"]["guide"]["cost"]
    assert set(search.GUIDES) == {"tavily", "brave"} and all(g["url"].startswith("https://") for g in search.GUIDES.values())


def test_search_settings_validation():
    with TestClient(main.app, headers=X) as o:
        login(o, "owner-search@x.io", "owner")
        assert o.put("/api/admin/settings", json={"search_provider": "google"}).status_code == 400
        r = o.put("/api/admin/settings", json={"search_provider": "brave"})
        assert r.status_code == 400 and "key" in r.json()["detail"]
        s = o.put("/api/admin/settings", json={"search_provider": "auto", "search_key": "BSA-test", "search_key_kind": "brave",
                                               "native_default_budget_usd": "2", "native_token_cap": "3000000"}).json()
        assert s["search_key_set"] and s["search_key_kind"] == "brave" and s["search_active"] == "brave" and "search_key_enc" not in s
        assert s["search_guides"]["tavily"]["url"].startswith("https://")
        assert s["native_default_budget_usd"] == "2" and s["native_token_cap"] == "3000000"
        assert o.put("/api/admin/settings", json={"native_default_budget_usd": "0"}).status_code == 400
        s = o.put("/api/admin/settings", json={"clear_search_key": True}).json()
        assert not s["search_key_set"] and s["search_active"] == "duckduckgo"


def test_fetch_blocks_internal_addresses_and_parses_duckduckgo(monkeypatch):
    for url in ("http://127.0.0.1:8080/api/admin/settings", "http://169.254.169.254/latest/meta-data", "file:///etc/passwd"):
        with pytest.raises(search.SearchError):
            search.fetch(url)
    html = ('<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fgso.gov.vn%2Fbao-cao&rut=x">Báo cáo <b>GSO</b></a>'
            '<a class="result__snippet" href="#">Dân số &amp; lao động</a>')
    monkeypatch.setattr(search.httpx, "post", lambda *a, **k: httpx.Response(200, text=html, request=httpx.Request("POST", "https://x")))
    db.set_setting("search_provider", "duckduckgo")
    try:
        assert search.search("dân số") == [{"title": "Báo cáo GSO", "url": "https://gso.gov.vn/bao-cao", "snippet": "Dân số & lao động"}]
    finally:
        db.set_setting("search_provider", "auto")


@pytest.mark.parametrize("tail, expect", [
    ("HTTP 402: Key limit exceeded (total limit). $1.03 of $1.00 used; does not reset.", "($1.03 / $1.00 đã dùng)"),
    ("HTTP 402: Insufficient Balance", "hết hạn mức / tín dụng"),
    ("budget: đã dùng 3.012 / 3 USD", "Đã chạm trần của lượt chạy (đã dùng 3.012 / 3 USD)"),
    ("HTTP 401: Authentication Fails, Your api key is invalid", "từ chối key"),
    ("Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 20, model: gemini-3.8-flash "
     "Please retry in 3h GenerateRequestsPerDayPerProjectPerModel-FreeTier", "gói miễn phí"),
    ("segfault", None)])
def test_failures_are_explained(tail, expect):
    msg = worker.explain_failure(tail, {"budget_usd": 2.5})
    assert (msg is None) if expect is None else (expect in msg), msg


def test_cli_cmd_has_no_token_budget(monkeypatch):
    monkeypatch.setattr(agents, "agent_binary", lambda e: ("/bin/claude", ["/bin/claude"]))
    c = worker.agent_cmd("claude", "p", "sonnet", 20, "/tmp/x")
    assert "--max-budget-usd" not in c and c[-2:] == ["--model", "sonnet"]


def test_unreadable_proxy_ca_is_copied_for_agent(tmp_path):
    if not sandbox.agent_ids():
        pytest.skip("không chạy bằng root hoặc không có user agent")
    locked = Path(tempfile.mkdtemp())
    locked.chmod(0o700)
    ca = locked / "proxy-ca.pem"
    ca.write_text("-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----\n")
    home = Path(tempfile.mkdtemp())
    old = os.environ.get("NODE_EXTRA_CA_CERTS")
    os.environ["NODE_EXTRA_CA_CERTS"] = str(ca)
    try:
        env = agents.env_for({"engine": "claude", "auth_mode": "account"}, home)
        assert env["NODE_EXTRA_CA_CERTS"].startswith(str(home)) and Path(env["NODE_EXTRA_CA_CERTS"]).read_text() == ca.read_text()
    finally:
        os.environ.pop("NODE_EXTRA_CA_CERTS") if old is None else os.environ.__setitem__("NODE_EXTRA_CA_CERTS", old)
