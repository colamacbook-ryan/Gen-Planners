#!/usr/bin/env python3
"""CLI agent giả lập cho test: nói đúng giao thức stream-json của claude/agy, hành vi chọn bằng FAKE_AGENT_MODE.

ok    — in vài sự kiện, đánh dấu từng stage done trong project.yaml, kết thúc bằng result + usage
slow  — chạy lâu (để test huỷ)
quota — báo lỗi 429 / hết quota
auth  — báo chưa đăng nhập
"""
import json
import os
import re
import sys
import time

if "--version" in sys.argv:
    print("9.9.9 (fake agent)")
    sys.exit(0)
mode = os.environ.get("FAKE_AGENT_MODE", "ok")
prompt = sys.argv[sys.argv.index("-p") + 1] if "-p" in sys.argv else ""
out = lambda ev: print(json.dumps(ev), flush=True)  # noqa: E731
if mode == "quota":
    print("Error 429: RESOURCE_EXHAUSTED — quota exceeded for this account", flush=True)
    sys.exit(1)
if mode == "auth":
    print("Authentication required. Please visit the URL to log in", flush=True)
    sys.exit(1)
if mode == "steal":                 # agent bị prompt-injection: thử lấy bí mật của máy chủ
    from pathlib import Path
    proj = Path(re.search(r"Dự án: (\S+)", prompt).group(1))
    data = proj.parents[2]
    targets = [data / "app.db", data / "fernet.key", data / "session.key", *[p / "idea.md" for p in proj.parent.iterdir() if p != proj]] \
        if os.access(proj.parent, os.R_OK) else [data / "app.db", data / "fernet.key", data / "session.key"]
    got, denied = [], []
    for t in targets:
        try:
            t.read_bytes()
            got.append(str(t))
        except OSError:
            denied.append(str(t))
    try:
        list(proj.parent.iterdir())
        got.append("list:" + str(proj.parent))
    except OSError:
        denied.append("list:" + str(proj.parent))
    (proj / "own.txt").write_text("agent ghi được trong dự án của mình")
    secrets = sorted(k for k in os.environ if k.startswith("GP_") and k != "GP_PROJECTS" or k.endswith(("_SECRET", "FERNET_KEY")))
    out({"type": "result", "result": json.dumps({"got": got, "denied": denied, "env": secrets}), "usage": {"input_tokens": 1, "output_tokens": 1}})
    sys.exit(0)
if mode == "slow":
    out({"type": "assistant", "message": {"content": [{"type": "text", "text": "Đang nghiên cứu rất lâu…"}]}})
    time.sleep(120)
    sys.exit(0)
d = re.search(r"Dự án: (\S+)", prompt).group(1)
out({"type": "system", "subtype": "init"})
out({"type": "assistant", "message": {"content": [{"type": "text", "text": "Đọc brief.md và playbook."}]}})
py = os.path.join(d, "project.yaml")
text = open(py).read()
for sid in re.findall(r'^\s+"?(\d\d-[\w-]+)"?: todo', text, re.M):
    text = re.sub(rf'^(\s+"?{sid}"?): todo', r"\1: done", text, flags=re.M)
    open(py, "w").write(text)
    out({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Edit", "input": {"file_path": py}}]}})
    time.sleep(0.05)
out({"type": "result", "result": "Đã xong: 12 stage, 0 lỗi.", "usage": {"input_tokens": 12000, "output_tokens": 3400}, "total_cost_usd": 0.42})
