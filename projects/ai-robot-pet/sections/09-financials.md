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

## Lợi nhuận theo mảng

{% with scenario = "base" %}{% include "partials/segments.md.j2" %}{% endwith %}


## Độ nhạy — biến nào quyết định kết quả

{% set b = fin.base %}
| Kịch bản | Thay đổi | Doanh thu {{ b.last.year }} | EBITDA {{ b.last.year }} | Tiền thấp nhất |
|---|---|---:|---:|---:|
| Cơ sở | — | {{ b.last.revenue|ty }} | {{ b.last.ebitda|ty }} | {{ b.metrics.min_cash|ty }} |
| Xấu | Sản lượng còn một nửa | {{ fin.bear.last.revenue|ty }} | {{ fin.bear.last.ebitda|ty }} | {{ fin.bear.metrics.min_cash|ty }} |
| Tốt | Sản lượng gấp rưỡi | {{ fin.bull.last.revenue|ty }} | {{ fin.bull.last.ebitda|ty }} | {{ fin.bull.metrics.min_cash|ty }} |
| CLB yếu | Doanh thu CLB, góc trải nghiệm chỉ đạt sáu phần mười; nhượng quyền một nửa | {{ fin.club_weak.last.revenue|ty }} | {{ fin.club_weak.last.ebitda|ty }} | {{ fin.club_weak.metrics.min_cash|ty }} |

- Trong kịch bản xấu, doanh nghiệp vẫn hoà vốn EBITDA năm {{ fin.bear.metrics.breakeven_year or "—" }} nhưng **tiền mặt chạm đáy {{ fin.bear.metrics.min_cash|ty }}** — tức cần thêm vốn hoặc cắt chi. Đây là lý do giải ngân theo cửa ải: kịch bản xấu sẽ lộ ra ngay ở giai đoạn 0–1, trước khi đổ phần lớn vốn.
- Biến nhạy nhất: **số pet bán ra** và **tỷ lệ pet còn hoạt động** ({{ a.pet_active|pct }}) — vì phụ kiện, gói kỹ năng, dịch vụ đều tính trên số pet đang dùng. CLB yếu làm chậm hoà vốn một năm nhưng không làm hỏng mô hình.
- Mọi con số trên là mô hình hoá từ giả định — giá trị của nó là cho thấy **cấu trúc** (mảng nào quan trọng, biến nào quyết định), không phải lời hứa doanh thu.

