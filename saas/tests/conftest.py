import os
import tempfile

os.environ.setdefault("GP_DATA", tempfile.mkdtemp(prefix="gp-test-"))

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _offline_key_check(monkeypatch):
    """Test không gọi nhà cung cấp thật khi lưu key: key chứa 'invalid' bị từ chối như HTTP 401, còn lại hợp lệ."""
    from saas.server import llm

    def fake(provider, key):
        if "invalid" in key:
            raise llm.LLMError("HTTP 401: invalid x-api-key", status=401)
        return ["model-a"]
    monkeypatch.setattr(llm, "list_models", fake)


@pytest.fixture(autouse=True)
def _fake_agent_env():
    """CLI giả lập chọn kịch bản qua FAKE_AGENT_MODE — cho biến này đi qua bộ lọc môi trường của sandbox."""
    from saas.server import sandbox
    sandbox.EXTRA_ALLOW.add("FAKE_AGENT_MODE")
    yield


@pytest.fixture(autouse=True)
def _reset_throttle():
    """Các test chạy chung một tiến trình: xoá bộ đếm chống dò mật khẩu giữa các test."""
    from saas.server import main
    main._attempts.clear()
    yield
