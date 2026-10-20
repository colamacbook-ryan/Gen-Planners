#!/usr/bin/env python3
"""Xuất một dự án thành JSON cho trình xem console / Gen Planner Studio.

  python tools/export.py <slug> [--out DIR] [--media-base URL]

Đọc projects/<slug>/: assumptions.yaml, evidence.yaml, sections/, deck.md (qua gen.py),
và nếu có: story.yaml, datasets.yaml, products.yaml, media/.
Ghi: <out>/project.json, dossier.json, documents.json (mặc định out = projects/<slug>/build/export).
Ảnh trong story/products ghi bằng tên file trong media/; --media-base là tiền tố URL khi phục vụ.
"""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import gen  # noqa: E402
import yaml  # noqa: E402


def vnum(x, d=0):
    return f"{x:,.{d}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--out")
    ap.add_argument("--media-base", default="media")
    args = ap.parse_args()
    d = gen.PROJECTS / args.slug
    out = Path(args.out) if args.out else d / "build" / "export"
    out.mkdir(parents=True, exist_ok=True)

    ctx, A, E = gen.context(d)
    env = gen.make_env(d, A, E, [])
    AV = A["assumptions"]
    n = A["meta"]["years"]

    def series(ref):
        if isinstance(ref, list) and ref and all(isinstance(r, str) for r in ref):
            res = [1.0] * n
            for r in ref:
                res = [a * b for a, b in zip(res, series(r))]
            return res
        if isinstance(ref, str) and ref.startswith("cum:"):
            res, acc = [], 0.0
            for x in series(ref[4:]):
                acc += x
                res.append(acc)
            return res
        return gen.per_year(AV[ref]["value"] if isinstance(ref, str) else ref, n)

    def media(v):
        if not v or str(v).startswith(("/", "http", "data:")):
            return v
        return f"{args.media_base.rstrip('/')}/{v}"

    def show(ref=None, val=None, fmt=None):
        if ref is not None:
            if ref not in AV:
                return "—"
            a = AV[ref]
            val = a["value"]
            fmt = fmt or ("pct" if a.get("unit") == "%" else None)
        if fmt == "pct":
            return vnum(val * 100) + "%"
        if fmt == "ty":
            return vnum(val / 1000, 1) + " tỷ đ"
        if fmt == "tr":
            return vnum(val) + " triệu đ"
        return vnum(val, 0 if float(val).is_integer() else 1)

    # ---- tài liệu
    sections = []
    for s in sorted((d / "sections").glob("*.md")):
        md = env.get_template(f"sections/{s.name}").render(**ctx)
        md = re.sub(r"^---\n.*?\n---\n", "", md, flags=re.S)
        m = re.search(r"^# (.+)$", md, re.M)
        sections.append(dict(key=s.stem, title=m.group(1) if m else s.stem, md=md.strip()))
    deck = re.sub(r"^---\n.*?\n---\n", "", env.get_template("deck.md").render(**ctx), flags=re.S)

    # ---- tài chính
    def yr(y):
        return {k: round(y[k], 1) for k in ("year", "revenue", "cogs", "gross_profit", "opex", "ebitda", "net_income", "capex", "fcf", "cash_end")}

    fin = {}
    for k, f in ctx["fin"].items():
        fin[k] = dict(years=[yr(y) for y in f["years"]],
                      metrics={m: (round(v, 3) if isinstance(v, float) else v) for m, v in f["metrics"].items()},
                      segments=[dict(id=g["id"], name=g["name"],
                                     revenue=[round(y["revenue"], 1) for y in g["years"]],
                                     contribution=[round(y["contribution"], 1) for y in g["years"]])
                                for g in f["segments"].values()])
    base = ctx["fin"]["base"]
    yrs = [y["year"] for y in base["years"]]

    def fill(t):
        t = t.replace("{breakeven}", str(fin["base"]["metrics"]["breakeven_year"]))
        return re.sub(r"\{(\w+)\}", lambda m: show(m.group(1)) if m.group(1) in AV else m.group(0), t)

    # ---- story (console)
    story = None
    if (d / "story.yaml").exists():
        story = yaml.safe_load(open(d / "story.yaml"))
        for h in story.get("headline", []):
            if "fin" in h:
                sc, _, key = h["fin"].split(".")
                h["value"] = show(val=fin[sc]["years"][-1][key], fmt=h.get("fmt"))
            else:
                h["value"] = show(h["ref"], fmt=h.get("fmt"))
            h["note"] = fill(h.get("note", ""))
        for f in story.get("forces", []):
            f["value"] = (f.get("prefix", "") + show(f["ref"], fmt=f.get("fmt"))) if "ref" in f else f.get("text", "")
            if "to_ref" in f:
                f["to_value"] = show(f["to_ref"], fmt=f.get("fmt"))
        for ph in story.get("phases", []):
            bv = AV.get(ph["budget_ref"], {}).get("value", 0)
            ph["budget"] = show(ph["budget_ref"], fmt="tr" if bv < 1000 else "ty")
            ph["criteria"] = [fill(c) for c in ph["criteria"]]
        story["images"] = {k: media(v) for k, v in (story.get("images") or {}).items()}
        con = story.get("console")
        if con and story.get("econ"):
            con["econ"] = economics(story["econ"], AV, base, ctx["fin"], series)

    # ---- dashboard
    dash = None
    if (d / "datasets.yaml").exists():
        dash = yaml.safe_load(open(d / "datasets.yaml"))
        dash["charts"] = dash.get("charts", []) + finance_charts(A, AV, base, ctx["fin"], yrs, series)

    # ---- sản phẩm
    products = yaml.safe_load(open(d / "products.yaml")) if (d / "products.yaml").exists() else []
    for p in products:
        if p.get("image"):
            p["image_url"] = media(p.pop("image"))

    assumptions = [dict(id=k, label=v.get("label"), value=v["value"], unit=v.get("unit"), status=v.get("status"),
                        confidence=v.get("confidence"), source=v.get("source") or [], note=v.get("note"))
                   for k, v in AV.items()]
    evidence = [dict(id=k, **{x: str(v.get(x)) for x in ("title", "publisher", "date", "url", "type", "note") if v.get(x)})
                for k, v in E.items()]
    st = {}
    for a in assumptions:
        st[a["status"]] = st.get(a["status"], 0) + 1
    p = ctx["p"]
    b = fin["base"]
    project = dict(id=args.slug, name=p["name"], status="done", version=ctx["version"],
                   updated=dt.datetime.now(dt.timezone.utc).isoformat(),
                   idea=(d / "idea.md").read_text(), stages=p.get("stages", {}), unit=A["meta"]["unit_label"],
                   kpi=dict(revenue_last=b["years"][-1]["revenue"], ebitda_last=b["years"][-1]["ebitda"], year_last=b["years"][-1]["year"],
                            breakeven=b["metrics"]["breakeven_year"], raise_total=b["metrics"]["raise_amount"],
                            phase0=AV.get("phase0_budget", {}).get("value"),
                            sources=len(evidence), assumptions=len(assumptions), by_status=st))
    json.dump(project, open(out / "project.json", "w"), ensure_ascii=False)
    json.dump(dict(dash=dash, story=story, fin=fin, assumptions=assumptions, evidence=evidence, products=products),
              open(out / "dossier.json", "w"), ensure_ascii=False)
    json.dump(dict(sections=sections, deck=deck), open(out / "documents.json", "w"), ensure_ascii=False)
    for f in sorted(out.iterdir()):
        print(f.name, f.stat().st_size)


def economics(spec, AV, base, F, series):
    """Giá trị một đơn vị cốt lõi so với chi phí có khách — cấu hình bằng story.econ."""
    v = lambda k: AV[k]["value"]
    Y = base["years"]
    i = spec.get("cac", {}).get("year_index", 2)
    cac = series(spec["cac"]["spend"])[i] / series(spec["cac"]["units"])[i]
    unit = v(spec["unit"]["price"]) * (1 - v(spec["unit"]["cogs"]))
    yearly = 0.0
    for item in spec.get("yearly", []):
        rate = 1.0
        for r in item["rate"]:
            rate *= v(r)
        yearly += rate * (1 - v(item["cogs"]))
    life = spec.get("life_years", 3)
    ltv = unit + yearly * life
    core = spec.get("core_stream")
    nonpet = sum(val for k, val in Y[-1]["streams"].items() if k != core) / Y[-1]["revenue"]
    return dict(cac=round(cac * 1000), dev=round(unit * 1000), eco_year=round(yearly * 1000), life_years=life, ltv=round(ltv * 1000),
                ratio=round(ltv / cac, 1), nonpet=round(nonpet * 100), gross=round(Y[-1]["gross_profit"] / Y[-1]["revenue"] * 100),
                year=Y[-1]["year"], rev_last=round(Y[-1]["revenue"] / 1000, 1), ebitda_last=round(Y[-1]["ebitda"] / 1000, 1),
                breakeven=base["metrics"]["breakeven_year"],
                share={s["seg"]: base["segments"][s["segment"]]["years"][-1]["revenue"] / 1000 for s in spec.get("share", [])},
                moic_base=round(F["base"]["metrics"]["investor_moic"], 1), moic_bear=round(F["bear"]["metrics"]["investor_moic"], 1))


def finance_charts(A, AV, base, F, yrs, series):
    M = A["model"]
    out = []
    phases = sorted(k for k in AV if re.fullmatch(r"phase\d_budget", k))
    if phases:
        out.append(dict(id="f1", group="finance", title="Vốn theo giai đoạn", type="bar", vertical=True, unit="triệu đ", status="estimate",
                        takeaway="Bước đầu chỉ cần một phần nhỏ tổng vốn; phần lớn tiền chỉ mở khi đã có số liệu thật.",
                        items=[dict(label=AV[k]["label"].split(" - ")[0], value=AV[k]["value"], tag="ours" if i == 0 else None) for i, k in enumerate(phases)],
                        sources=[dict(t="assumptions.yaml", u="")]))
    opex_items = [(o["name"], series(o["amount"])) for o in M["opex"]]
    big = max(opex_items, key=lambda x: x[1][-1])[0] if opex_items else ""
    out.append(dict(id="f2", group="finance", title="Chi phí vận hành theo hạng mục", type="stacked", unit="tỷ đ", status="model",
                    takeaway=f"Khoản chi phí vận hành lớn nhất năm cuối: {big}.",
                    categories=[str(y) for y in yrs],
                    series=[dict(name=nm, values=[round(x / 1000, 2) for x in vals]) for nm, vals in opex_items],
                    sources=[dict(t="assumptions.yaml", u="")]))
    y5 = base["years"][-1]
    steps = [dict(label="Doanh thu", value=round(y5["revenue"] / 1000, 1), kind="total"), dict(label="Giá vốn", value=-round(y5["cogs"] / 1000, 1))]
    steps += [dict(label=nm, value=-round(vals[-1] / 1000, 1)) for nm, vals in opex_items if vals[-1]]
    steps += [dict(label="Thuế TNDN", value=-round(y5["tax"] / 1000, 1)), dict(label="Lợi nhuận ròng", value=round(y5["net_income"] / 1000, 1), kind="total")]
    out.append(dict(id="f3", group="finance", title=f"Từ doanh thu tới lợi nhuận, năm {yrs[-1]}", type="waterfall", unit="tỷ đ", status="model",
                    takeaway=f"Lợi nhuận ròng năm cuối khoảng {vnum(y5['net_income'] / 1000, 1)} tỷ đ trên doanh thu {vnum(y5['revenue'] / 1000, 1)} tỷ đ.",
                    steps=steps, sources=[dict(t="model", u="")]))
    nm = dict(bear="Xấu", base="Cơ sở", bull="Tốt")
    worst = min(F.items(), key=lambda kv: kv[1]["metrics"]["min_cash"])
    out.append(dict(id="f4", group="finance", title="Tiền mặt cuối năm theo kịch bản", type="line", unit="tỷ đ", status="model",
                    takeaway=(f"Kịch bản '{nm.get(worst[0], worst[0])}' chạm đáy {vnum(worst[1]['metrics']['min_cash'] / 1000, 1)} tỷ đ — "
                              "vì vậy giải ngân theo cửa ải."),
                    series=[dict(name=nm.get(k, k), points=[[y["year"], round(y["cash_end"] / 1000, 2), "model"] for y in f["years"]]) for k, f in F.items()],
                    sources=[dict(t="model", u="")]))
    segs = list(base["segments"].values())
    out.append(dict(id="f5", group="finance", title="Doanh thu theo mảng", type="stacked", unit="tỷ đ", status="model",
                    takeaway=f"Mảng lớn nhất năm cuối: {max(segs, key=lambda g: g['last']['revenue'])['name']}.",
                    categories=[str(y) for y in yrs], series=[dict(name=g["name"], values=[round(y["revenue"] / 1000, 2) for y in g["years"]]) for g in segs],
                    sources=[dict(t="model", u="")]))
    srt = sorted(segs, key=lambda g: -g["last"]["margin"])
    out.append(dict(id="f6", group="finance", title=f"Biên đóng góp theo mảng, năm {yrs[-1]}", type="bar", unit="%", status="model",
                    takeaway=f"Biên cao nhất: {srt[0]['name']}; thấp nhất: {srt[-1]['name']}.",
                    items=[dict(label=g["name"], value=round(g["last"]["margin"] * 100, 1)) for g in srt], sources=[dict(t="model", u="")]))
    core = [s["id"] for s in M["revenue_streams"] if s.get("core")]
    if core:
        a = [sum(v for k, v in y["streams"].items() if k in core) for y in base["years"]]
        rest = [y["revenue"] - x for y, x in zip(base["years"], a)]
        out.append(dict(id="f7", group="finance", title="Doanh thu hệ sinh thái so với sản phẩm cốt lõi", type="stacked", unit="tỷ đ", status="model",
                        takeaway=f"Năm cuối {round(rest[-1] / base['years'][-1]['revenue'] * 100)}% doanh thu đến từ hệ sinh thái quanh sản phẩm cốt lõi.",
                        categories=[str(y) for y in yrs],
                        series=[dict(name="Hệ sinh thái", values=[round(v / 1000, 2) for v in rest]), dict(name="Sản phẩm cốt lõi", values=[round(v / 1000, 2) for v in a])],
                        sources=[dict(t="model", u="")]))
    return out


if __name__ == "__main__":
    main()
