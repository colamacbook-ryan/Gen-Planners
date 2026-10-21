"""Chạy Plan bằng key người dùng: OpenRouter qua Claude Code, trần chi phí, lỗi hết tín dụng/key sai được giải thích rõ,
chứng chỉ CA proxy đọc được bởi user cô lập."""
import os
import tempfile
from pathlib import Path

os.environ.setdefault("GP_DATA", tempfile.mkdtemp(prefix="gp-test-"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from saas.server import agents, db, main, sandbox, worker  # noqa: E402

X = {"X-GP": "1"}


def test_openrouter_key_drives_claude_code(tmp_path):
    env = agents.env_for({"engine": "claude", "auth_mode": "api_key"}, tmp_path, "sk-or-v1-abc", "anthropic/claude-haiku-5.5")
    assert env["ANTHROPIC_BASE_URL"] == "https://openrouter.ai/api" and env["ANTHROPIC_AUTH_TOKEN"] == "sk-or-v1-abc"
    assert env["ANTHROPIC_API_KEY"] == "" and all(env[s] == "anthropic/claude-haiku-5.5" for s in agents.MODEL_SLOTS)
    plain = agents.env_for({"engine": "claude", "auth_mode": "api_key"}, tmp_path, "sk-ant-xyz")
    assert plain["ANTHROPIC_API_KEY"] == "sk-ant-xyz" and "ANTHROPIC_BASE_URL" not in plain


def test_budget_flag_and_prompt_note():
    cmd = worker.agent_cmd.__wrapped__ if hasattr(worker.agent_cmd, "__wrapped__") else worker.agent_cmd
    orig = agents.agent_binary
    agents.agent_binary = lambda e: ("/bin/claude", ["/bin/claude"])
    try:
        c = cmd("claude", "p", "anthropic/claude-haiku-5.5", 20, "/tmp/x", 2.5)
        assert c[c.index("--max-budget-usd") + 1] == "2.5" and c[-2:] == ["--model", "anthropic/claude-haiku-5.5"]
        assert "--max-budget-usd" not in cmd("claude", "p", None, 20, "/tmp/x")
    finally:
        agents.agent_binary = orig
    assert "3 subagent" in worker.BUDGET_NOTE.format(budget=2.5)


@pytest.mark.parametrize("tail, expect", [
    ("API Error: 403 Key limit exceeded (total limit). $1.03 of $1.00 used; does not reset.", "($1.03 / $1.00 đã dùng)"),
    ("Your credit balance is too low to access the Anthropic API", "hết hạn mức / tín dụng"),
    ("Error: Reached max budget ($2.50)", "trần chi phí 2.5 USD"),
    ("Invalid API key · Please run /login 401", "từ chối key"),
    ("Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 20, model: gemini-3.8-flash "
     "Please retry in 3h GenerateRequestsPerDayPerProjectPerModel-FreeTier", "gói miễn phí"),
    ("segfault", None)])
def test_failures_are_explained(tail, expect):
    msg = worker.explain_failure(tail, {"budget_usd": 2.5})
    assert (msg is None) if expect is None else (expect in msg), msg


def test_run_validates_openrouter_model_and_budget():
    with TestClient(main.app, headers=X) as u:
        if u.post("/api/auth/signup", json={"email": "or@x.io", "password": "password1"}).status_code != 200:
            u.post("/api/auth/login", json={"email": "or@x.io", "password": "password1"})
        db.set_setting("plan_billing", "either")
        k = u.post("/api/keys", json={"provider": "openrouter", "key": "sk-or-v1-testkey-000000", "model": "openai/gpt-5"}).json()
        assert u.get("/api/keys").json()[0]["plan_engine"] == "claude"
        slug = u.post("/api/projects", json={"name": "OR", "idea": "Dự án thử chạy Plan bằng key OpenRouter của người dùng."}).json()["slug"]
        r = u.post(f"/api/projects/{slug}/run", json={"billing": "user_key", "api_key_id": k["id"], "model": "openai/gpt-5", "force": True})
        assert r.status_code == 400 and "anthropic/" in r.json()["detail"]
        for bad in ("abc", "0", "5000"):
            r = u.post(f"/api/projects/{slug}/run", json={"billing": "user_key", "api_key_id": k["id"], "budget_usd": bad, "force": True})
            assert r.status_code == 400, bad
        r = u.post(f"/api/projects/{slug}/run", json={"billing": "user_key", "api_key_id": k["id"], "budget_usd": "2,5", "force": True})
        assert r.status_code == 200
        j = db.one("SELECT * FROM jobs WHERE id=?", (r.json()["job_id"],))
        assert j["model"] == agents.OPENROUTER_DEFAULT_PLAN_MODEL and j["budget_usd"] == 2.5     # model không phải anthropic → mặc định an toàn
        u.post(f"/api/jobs/{j['id']}/cancel")


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
        env = agents.env_for({"engine": "claude", "auth_mode": "api_key"}, home, "sk-ant-x")
        assert env["NODE_EXTRA_CA_CERTS"].startswith(str(home)) and Path(env["NODE_EXTRA_CA_CERTS"]).read_text() == ca.read_text()
    finally:
        os.environ.pop("NODE_EXTRA_CA_CERTS") if old is None else os.environ.__setitem__("NODE_EXTRA_CA_CERTS", old)
