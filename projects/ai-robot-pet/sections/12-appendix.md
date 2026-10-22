# Phụ lục

## Nghiên cứu gốc (kèm nguồn đầy đủ)

| Mã | Nội dung | File |
|---|---|---|
| R1 | Thị trường AI companion/AI toy toàn cầu & Trung Quốc | research/01-global-market.md |
| R2 | Nguồn hàng TQ, BOM, chi phí cloud, logistics, landed cost | research/02-supply-cost.md |
| R3 | Pháp lý, thuế, hợp quy, dữ liệu, ưu đãi | research/03-legal-tax.md |
| R4 | Cầu Việt Nam: dân số, đồ chơi, thú cưng, giáo dục, thái độ với AI | research/04-vn-demand.md |
| R5 | CLB trải nghiệm & nhượng quyền: số liệu so sánh, P&L 1 CLB | research/05-club-franchise.md |
| R6 | Bản đồ use-case & khoảng trống ở VN, thí nghiệm | research/06-use-cases.md |
| R7 | Tín hiệu dài hạn 5–15 năm, xếp hạng vùng đất | research/07-frontier.md |

## Danh sách nguồn

{% for k, v in ev.items() %}
- **{{ k }}** — {{ v.title }}{% if v.get('publisher') %} · {{ v.publisher }}{% endif %}{% if v.get('date') %} · {{ v.date }}{% endif %}{% if v.get('url') %} · <{{ v.url }}>{% endif %}

{% endfor %}

## Tổng hợp việc cần người thật làm

1. RFQ 3–5 nhà máy OEM Thâm Quyến; đặt mẫu; chuyến khảo sát.
2. Phỏng vấn/thử nghiệm: 20 gia đình (tiếng Anh), 15 gia đình (người già), 2 trung tâm STEM, 15 thương hiệu thiết bị.
3. Đại lý hải quan: xác định trước mã HS; lab: báo giá hợp quy.
4. Luật sư: luồng dữ liệu cá nhân, đánh giá chuyển dữ liệu xuyên biên giới, điều lệ + thoả thuận cổ đông.
