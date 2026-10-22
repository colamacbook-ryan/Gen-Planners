# Dự phóng tài chính

Toàn bộ số liệu sinh tự động từ `assumptions.yaml` (xem file Excel kèm theo).

## Kịch bản cơ sở (base)

{% with scenario = "base" %}{% include "partials/pnl.md.j2" %}{% endwith %}


## So sánh kịch bản

| Chỉ số | {% for k in fin %}{{ k }} | {% endfor %}

|---|{% for k in fin %}---:|{% endfor %}

| Doanh thu năm cuối | {% for k, f in fin.items() %}{{ f.last.revenue|num }} | {% endfor %}

| EBITDA năm cuối | {% for k, f in fin.items() %}{{ f.last.ebitda|num }} | {% endfor %}

| Năm hòa vốn EBITDA | {% for k, f in fin.items() %}{{ f.metrics.breakeven_year or "—" }} | {% endfor %}

| Tiền thấp nhất | {% for k, f in fin.items() %}{{ f.metrics.min_cash|num }} | {% endfor %}

| NPV | {% for k, f in fin.items() %}{{ f.metrics.npv|num }} | {% endfor %}

| MOIC nhà đầu tư | {% for k, f in fin.items() %}{{ f.metrics.investor_moic|num(1) }}x | {% endfor %}


## Giả định chính

| Giả định | Giá trị | Trạng thái | Nguồn |
|---|---|---|---|
{% for k, v in A.items() %}
| {{ v.label }} | {{ v.value }} {{ v.unit }} | {{ v.status }} / {{ v.confidence }} | {{ (v.source or [])|join(", ") or "—" }} |
{% endfor %}

TODO(stage 09): phân tích độ nhạy.
