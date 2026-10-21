"""Model tài chính: bất biến kế toán trên model sinh ngẫu nhiên + lỗi cấu trúc phải được báo rõ (không âm thầm ra số sai)."""
import copy
import random
import sys

import pytest
import yaml

from saas.server.config import ROOT

sys.path.insert(0, str(ROOT))
import gen  # noqa: E402

BASE = yaml.safe_load((ROOT / "projects" / "ai-robot-pet" / "assumptions.yaml").read_text())


def rand_model(rng):
    n = rng.randint(1, 8)
    A, M = {}, {}
    num = lambda lo, hi: [round(rng.uniform(lo, hi), 2) for _ in range(n)] if rng.random() < .5 else round(rng.uniform(lo, hi), 2)
    streams = []
    for i in range(rng.randint(1, 5)):
        for k, (lo, hi) in {"p": (0, 500), "v": (0, 2000), "c": (0, 1)}.items():
            A[f"{k}{i}"] = {"value": num(lo, hi)}
        streams.append({"id": f"s{i}", "segment": f"g{i % 2}", "price": f"p{i}",
                        "volume": rng.choice([f"v{i}", f"cum:v{i}", [f"v{i}", f"c{i}"]]), "cogs_pct": f"c{i}",
                        "kind": rng.choice(["recurring", "one_off"])})
    A["opx"] = {"value": num(0, 50000)}
    A["cap"] = {"value": num(0, 5000)}
    A["tax"] = {"value": [rng.choice([0, .1, .2]) for _ in range(n)]}
    for k, v in {"raise": rng.uniform(0, 1e5), "fc": rng.uniform(0, 1e4), "pre": rng.uniform(1, 1e5), "dr": .2, "mult": rng.uniform(1, 12)}.items():
        A[k] = {"value": v}
    M = {"segments": {"g0": "A", "g1": "B"}, "revenue_streams": streams,
         "opex": [{"name": "o", "amount": "opx", "segment": rng.choice([None, "g0"])}],
         "capex": "cap", "tax_rate": "tax", "funding": "raise", "founder_capital": "fc", "pre_money": "pre",
         "discount_rate": "dr", "exit_multiple": "mult", "exit_basis": rng.choice(["ebitda", "recurring_ebitda"]),
         "scenarios": {"base": {}, "bear": {"volume_x": .7, "price_x": .9, "opex_x": 1.1}, "s0_off": {"stream_x": {"s0": 0}}}}
    return {"meta": {"start_year": 2027, "years": n}, "assumptions": A, "model": M}


@pytest.mark.parametrize("seed", range(300))
def test_accounting_invariants(seed):
    A = rand_model(random.Random(seed))
    assert validate(A) == []
    F = gen.compute_all(A)
    for f in F.values():
        m = f["metrics"]
        cash = m["raise_amount"] + m["founder_capital"]
        for y in f["years"]:
            ap = pytest.approx
            assert y["revenue"] == ap(sum(y["streams"].values()))
            assert y["revenue_recurring"] + y["revenue_one_off"] == ap(y["revenue"])
            assert y["gross_profit"] == ap(y["revenue"] - y["cogs"])
            assert y["ebitda"] == ap(y["gross_profit"] - y["opex"])
            assert y["ebitda_recurring"] == ap(y["ebitda"] - y["gp_one_off"])
            assert y["tax"] >= 0 and y["net_income"] <= y["ebitda"] + 1e-9
            assert y["fcf"] == ap(y["net_income"] - y["capex"])
            cash += y["fcf"]
            assert y["cash_end"] == ap(cash)
            assert 0 <= y["recurring_share"] <= 1 + 1e-9
        assert sum(sum(s["revenue"] for s in g["years"]) for g in f["segments"].values()) == pytest.approx(sum(y["revenue"] for y in f["years"]))
        assert m["funding_gap"] == pytest.approx(max(0, -m["min_cash"]))
        assert m["exit_value"] >= 0 and m["exit_ebitda"] <= f["last"]["ebitda"] + 1e-9
    assert F["s0_off"]["years"][-1]["streams"]["s0"] == 0


def validate(A):
    return gen.validate_model(A)[0]


def mut(fn):
    A = copy.deepcopy(BASE)
    fn(A, A["model"])
    return " | ".join(validate(A))


@pytest.mark.parametrize("fn, expect", [
    (lambda A, M: M["scenarios"].update(x={"stream_x": {"pett": .5}}), "không có dòng doanh thu 'pett'"),
    (lambda A, M: M["scenarios"].update(y={"volum_x": .5}), "'volum_x' không hợp lệ"),
    (lambda A, M: M.update(scenarios={"bear": {}}), "phải có kịch bản 'base'"),
    (lambda A, M: M["revenue_streams"][0].update(price="nope"), "'nope' không có trong assumptions"),
    (lambda A, M: M["revenue_streams"][0].update(volume=["cum:nope", "pet_units"]), "'nope' không có trong assumptions"),
    (lambda A, M: M["revenue_streams"].append(dict(M["revenue_streams"][0])), "bị trùng"),
    (lambda A, M: M["opex"][0].update(segment="zzz"), "segment 'zzz'"),
    (lambda A, M: A["assumptions"]["pet_price"].update(value="abc"), "phải là số"),
    (lambda A, M: A["assumptions"]["pet_price"].update(value=None), "phải là số"),
    (lambda A, M: A["assumptions"]["pet_price"].update(value=True), "phải là số"),
    (lambda A, M: A["assumptions"]["pet_cogs"].update(value=1.5), "tỷ lệ giá vốn"),
    (lambda A, M: A["meta"].update(years=0), "meta.years"),
    (lambda A, M: M.pop("capex"), "thiếu capex"),
    (lambda A, M: M["scenarios"].update(z={"volume_x": "nhiều"}), "hệ số phải là số"),
])
def test_model_structure_errors(fn, expect):
    assert expect in mut(fn)


def test_real_models_are_valid():
    assert validate(BASE) == []
    tpl = yaml.safe_load((ROOT / "templates" / "project" / "assumptions.yaml").read_text())
    assert validate(tpl) == []
