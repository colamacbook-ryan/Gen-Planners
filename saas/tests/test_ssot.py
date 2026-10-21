"""Bộ sửa số liệu không bao giờ được làm hỏng SSOT: chỉ đúng một giá trị đổi, comment còn nguyên khi sửa được tại dòng."""
import os
import shutil
import tempfile

os.environ.setdefault("GP_DATA", tempfile.mkdtemp(prefix="gp-test-"))

import pytest  # noqa: E402
import yaml  # noqa: E402

from saas.server import ssot  # noqa: E402
from saas.server.config import ROOT, WORKSPACE  # noqa: E402
import sys  # noqa: E402
sys.path.insert(0, str(ROOT))

TRICKY = """# đầu file
meta: {start_year: 2027, years: 5}
assumptions:
  # nhóm A
  a_note_braces: {label: "Giá {cao} nhất, có phẩy", value: 10, unit: "%", status: estimate, source: [], note: "value: 99 {x}"}
  a_label_value: {label: "value: giả", value: [1, 2, 3], unit: x, status: estimate, source: []}
  a_float: {label: F, value: 0.25, unit: "%", status: placeholder, source: [ev-1]}
  a_block:
    label: Khối nhiều dòng
    value: 7
    status: estimate
  a_text: {label: T, value: abc, status: estimate, source: []}
model:
  a_note_braces: {value: 1}
"""


def proj(name, text=None):
    d = WORKSPACE / name
    shutil.rmtree(d, ignore_errors=True)
    if text is None:
        shutil.copytree(ROOT / "projects" / "ai-robot-pet", d, ignore=shutil.ignore_patterns("build", "media", "research"))
    else:
        d.mkdir(parents=True)
        (d / "assumptions.yaml").write_text(text)
    return d


def test_every_real_assumption_roundtrips():
    d = proj("fuzz-real")
    before = yaml.safe_load((d / "assumptions.yaml").read_text())
    n = 0
    for key, a in before["assumptions"].items():
        v = a.get("value")
        if isinstance(v, bool) or not isinstance(v, (int, float, list)) or (isinstance(v, list) and not all(isinstance(x, (int, float)) for x in v)):
            continue
        new = [x * 2 + 1 for x in v] if isinstance(v, list) else v * 2 + 1
        ssot.set_value("fuzz-real", key, new)
        after = yaml.safe_load((d / "assumptions.yaml").read_text())
        exp = yaml.safe_load(yaml.safe_dump(before))
        exp["assumptions"][key]["value"] = new
        assert after == exp, key                                    # không giả định nào khác bị đụng tới
        before = after
        n += 1
    text = (d / "assumptions.yaml").read_text()
    assert n > 50 and "# SINGLE SOURCE OF TRUTH" in text and "# ---" in text   # comment còn nguyên sau >50 lần sửa


@pytest.mark.parametrize("key,new,ok", [
    ("a_note_braces", 12, True), ("a_label_value", "4 5 6", True), ("a_label_value", [1, 2], False),
    ("a_float", "0,5", True), ("a_block", 8, True), ("a_text", 3, False), ("missing", 1, False), ("a_float", "abc", False)])
def test_tricky_lines(key, new, ok):
    d = proj("fuzz-tricky", TRICKY)
    if not ok:
        with pytest.raises(ssot.SSOTError):
            ssot.set_value("fuzz-tricky", key, new)
        assert (d / "assumptions.yaml").read_text() == TRICKY        # lỗi thì file không đổi
        return
    r = ssot.set_value("fuzz-tricky", key, new)
    after = yaml.safe_load((d / "assumptions.yaml").read_text())
    exp = yaml.safe_load(TRICKY)
    exp["assumptions"][key]["value"] = r["value"]
    assert after == exp
    assert after["model"]["a_note_braces"] == {"value": 1}             # khoá trùng tên ngoài khối assumptions không bị sửa
    if key != "a_block":
        assert "# nhóm A" in (d / "assumptions.yaml").read_text()


def test_status_rules():
    proj("fuzz-st", TRICKY)
    with pytest.raises(ssot.SSOTError):
        ssot.set_value("fuzz-st", "a_note_braces", 1, "verified")     # chưa có nguồn
    ssot.set_value("fuzz-st", "a_float", 0.3, "verified")             # có nguồn → được
    a = yaml.safe_load((WORKSPACE / "fuzz-st" / "assumptions.yaml").read_text())["assumptions"]["a_float"]
    assert a["status"] == "verified" and a["value"] == 0.3
    with pytest.raises(ssot.SSOTError):
        ssot.set_value("fuzz-st", "a_float", 0.3, "bịa")


def test_datasets_schema_check(tmp_path):
    """Lỗi agent thật gặp: dấu phẩy trong flow-mapping tách giá trị thành khoá rác; bar viết 'series' thay vì 'items'."""
    import gen
    (tmp_path / "datasets.yaml").write_text("""
kpis:
  - {label: Thuê, value: 66,8 USD/m², note: JLL}
  - {label: Đúng, value: "66,8 USD/m²"}
charts:
  - {id: m1, type: bar, series: [{name: x, points: [[a, 1]]}]}
  - {id: m2, type: bar, items: [{label: a, value: 1}]}
  - {id: m3, type: grouped, categories: [a, b], series: [{name: s, values: [1]}]}
  - {id: m4, type: pie, items: []}
""")
    errs = gen.check_datasets(tmp_path)
    assert any("kpis[0]" in e and "ngoặc kép" in e for e in errs)
    assert not any("kpis[1]" in e for e in errs)
    assert any("m1" in e and "items" in e for e in errs) and not any("m2" in e for e in errs)
    assert any("m3" in e and "2 giá trị" in e for e in errs) and any("m4" in e and "không hỗ trợ" in e for e in errs)
    assert gen.check_datasets(ROOT / "projects" / "ai-robot-pet") == []          # dự án mẫu đúng chuẩn


def test_verified_needs_external_source_and_sanity_warnings(tmp_path, capsys):
    import gen
    d = proj("rule-verified")
    ev = (d / "evidence.yaml").read_text() + '\nev-founder-brief: {title: Lời founder trong brief, type: founder}\n'
    (d / "evidence.yaml").write_text(ev)
    a = (d / "assumptions.yaml").read_text().replace("source: [ev-caixin-aitoy]}", "source: [ev-founder-brief]}", 1)
    (d / "assumptions.yaml").write_text(a)
    gen.PROJECTS = WORKSPACE
    assert gen.cmd_check("rule-verified", as_json=True) == 1
    out = capsys.readouterr().out.strip().splitlines()[-1]
    r = __import__("json").loads(out)
    assert any("nguồn nội bộ/lời founder" in e for e in r["errors"])
    assert any("bear" in w for w in r["warnings"])                         # kịch bản xấu thiếu tiền được nhắc


def test_history_versions_and_restore():
    from saas.server import history
    d = proj("hist")
    history.ensure("hist")
    p = d / "assumptions.yaml"
    p.write_text(p.read_text().replace("value: 3.49", "value: 3.99", 1))
    rev = history.commit("hist", "Đổi giá", "a@x.io")
    assert rev and history.commit("hist", "không đổi gì") is None
    (d / "sections" / "02-market.md").unlink()
    history.commit("hist", "Xoá nhầm")
    history.restore("hist", rev, "a@x.io")
    assert (d / "sections" / "02-market.md").exists() and "3.99" in p.read_text()
    msgs = [v["message"] for v in history.log("hist")]
    assert msgs[:3] == [f"Khôi phục về phiên bản {rev}", "Xoá nhầm", "Đổi giá"] and history.log("hist")[2]["who"] == "a@x.io"
    import pytest
    with pytest.raises(ValueError):
        history.show("hist", "../etc")


def test_one_off_revenue_split_and_exit_basis(capsys):
    """Doanh thu bán một lần (thiết bị, phí gia nhập) tách khỏi định kỳ; định giá có thể chỉ tính EBITDA định kỳ."""
    import json
    import gen
    gen.PROJECTS = WORKSPACE
    d = proj("rule-oneoff")
    src = (d / "assumptions.yaml").read_text()
    one = src.replace("cogs_pct: pet_cogs, core: true}", "cogs_pct: pet_cogs, core: true, kind: one_off}")
    A0, A1 = yaml.safe_load(src), yaml.safe_load(one)
    b0, b1 = gen.compute_all(A0)["base"], gen.compute_all(A1)["base"]
    for y0, y1 in zip(b0["years"], b1["years"]):
        assert y0["revenue"] == y1["revenue"] and y0["ebitda"] == y1["ebitda"]      # tổng P&L không đổi
        assert y1["revenue_one_off"] == pytest.approx(y1["streams"]["pet"])
        assert y1["revenue_recurring"] + y1["revenue_one_off"] == pytest.approx(y1["revenue"])
        assert y1["ebitda_recurring"] < y1["ebitda"]
    assert b0["metrics"]["recurring_share"] == 1 and b1["metrics"]["recurring_share"] < 1
    assert b1["metrics"]["exit_value"] == b0["metrics"]["exit_value"]                  # mặc định vẫn ×EBITDA tổng
    A1["model"]["exit_basis"] = "recurring_ebitda"
    b2 = gen.compute_all(A1)["base"]
    assert b2["metrics"]["exit_ebitda"] == b2["last"]["ebitda_recurring"]
    assert b2["metrics"]["exit_value"] < b0["metrics"]["exit_value"]

    (d / "assumptions.yaml").write_text(one)                                           # lint nhắc khi một lần > 20% mà vẫn ×EBITDA tổng
    gen.cmd_check("rule-oneoff", as_json=True)
    r = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert not r["errors"] and any("exit_basis: recurring_ebitda" in w for w in r["warnings"])
    (d / "assumptions.yaml").write_text(one.replace("kind: one_off", "kind: once"))
    assert gen.cmd_check("rule-oneoff", as_json=True) == 1
    r = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert any("kind 'once' không hợp lệ" in e for e in r["errors"])
