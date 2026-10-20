---
title: "{{ p.name }} — Hồ sơ dự án"
subtitle: "Phiên bản {{ version }} · {{ today }}"
---

{% include "partials/draft.md.j2" %}

# Tóm tắt điều hành

**One-liner:** TODO(stage 01)

**Kill assumptions** (sai là dự án dừng):

1. TODO(stage 01)

**Con số chính (kịch bản base):** gọi vốn {{ fin.base.metrics.raise_amount|money }} cho {{ fin.base.metrics.investor_stake|pct(1) }} cổ phần;
doanh thu năm {{ fin.base.last.year }} đạt {{ fin.base.last.revenue|money }}, hòa vốn EBITDA năm {{ fin.base.metrics.breakeven_year or "chưa đạt" }}.
