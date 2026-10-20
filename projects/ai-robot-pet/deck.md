---
title: "{{ p.name }}"
subtitle: "Hồ sơ gọi vốn · v{{ version }}"
date: "{{ today }}"
---

## Vấn đề

TODO(stage 12)

## Giải pháp

TODO(stage 12)

## Thị trường

TODO(stage 12)

## Sản phẩm

TODO(stage 12)

## Mô hình kinh doanh

TODO(stage 12)

## Bằng chứng & traction

TODO(stage 12)

## Đối thủ

TODO(stage 12)

## Go-to-market

TODO(stage 12)

## Tài chính (kịch bản base, {{ meta.unit_label }})

{% with scenario = "base" %}{% include "partials/pnl.md.j2" %}{% endwith %}


## Ba kịch bản

{% for k, f in fin.items() %}
- **{{ k }}**: doanh thu năm {{ f.last.year }} {{ f.last.revenue|money }} · hòa vốn {{ f.metrics.breakeven_year or "chưa đạt" }} · MOIC {{ f.metrics.investor_moic|num(1) }}x
{% endfor %}

## Đội ngũ

TODO(stage 12)

## Gọi vốn

- Cần: **{{ fin.base.metrics.raise_amount|money }}** cho {{ fin.base.metrics.investor_stake|pct(1) }}
- Định giá trước vốn {{ fin.base.metrics.pre_money|money }}
- TODO(stage 10): use of funds

{% if draft %}
## Lưu ý

{% include "partials/draft.md.j2" %}
{% endif %}
