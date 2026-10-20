import os
import tempfile

os.environ.setdefault("GP_DATA", tempfile.mkdtemp(prefix="gp-test-"))

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_throttle():
    """Các test chạy chung một tiến trình: xoá bộ đếm chống dò mật khẩu giữa các test."""
    from saas.server import main
    main._attempts.clear()
    yield
