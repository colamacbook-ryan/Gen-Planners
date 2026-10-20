---
title: "{{ p.name }}"
subtitle: "Bộ não AI tiếng Việt cho thiết bị biết nói · v{{ version }}"
date: "{{ today }}"
---
{% set b = fin.base %}

## Mọi đồ vật sắp biết nói chuyện

- Phần cứng đã rẻ: thiết bị giọng nói về kho khoảng {{ a.fact_landed_low }} USD
- AI nghe–nói đã rẻ: dưới {{ a.fact_cloud_selfhost }} USD/người/tháng khi tự vận hành
- Trung Quốc: thị trường AI toy {{ a.fact_cn_aitoy_2025 }} tỷ NDT (2025) → tới {{ a.fact_cn_aitoy_2030 }} tỷ NDT (2030), hơn {{ a.fact_cn_aitoy_firms|num }} công ty
- **Câu hỏi: ai làm bộ não tiếng Việt cho chúng?**

## Thứ đã thắng ở Trung Quốc

- Fuzozo: {{ a.fact_fuzozo_units|num }} máy, {{ a.fact_fuzozo_minutes }} phút/ngày/người dùng
- {{ a.fact_fuzozo_female|pct }} người dùng cốt lõi là nữ trưởng thành → nhu cầu là **bạn đồng hành**
- Một nền tảng bộ não (Doubao) chạy trên hơn {{ a.fact_doubao_devices|num }} thiết bị
- Mặt tối: trả hàng {{ a.fact_return_rate|pct }} vì hết hứng thú → **người giữ chân được người dùng mới thắng**

## Việt Nam: 3 lực cấu trúc

- **Già hoá:** {{ a.fact_vn_60plus }} triệu người 60+ → {{ a.fact_vn_60plus_2050 }} triệu năm 2050
- **Giáo dục:** AI vào mọi trường từ 2026-27; tiếng Anh là ngôn ngữ thứ hai tới 2035
- **Luật:** dữ liệu trẻ em & AI bị siết từ 2026 → server tại VN là lợi thế
- **Độ trễ:** robot hút bụi VN +{{ a.fact_vn_vacuum_growth|pct }}/năm, hãng TQ áp đảo

## Khoảng trống

- Chưa có sản phẩm hay nền tảng AI đồng hành **nói tiếng Việt** ở cấp tiêu dùng
- Hãng TQ có vỏ máy, không có tiếng Việt, không tuân thủ luật VN
- Viettel/FPT làm hạ tầng giọng nói, không làm tính cách + nội dung + an toàn cho người già/trẻ em

## Giải pháp: một bộ não, nhiều thân

- **Bộ não** (server tại VN): giọng tiếng Việt 3 miền · tính cách & trí nhớ · bộ lọc an toàn · nội dung
- **Thân** mua OEM Thâm Quyến, firmware mở
- Chứng minh bằng 2 sản phẩm của mình → cấp phép cho hãng khác

## Hai sản phẩm đầu tiên

- **"Con cháu":** bạn trò chuyện cho bố mẹ ở quê; con cái nhận tóm tắt, cảnh báo — {{ a.elder_price|money(2) }} + thuê bao
- **Bạn luyện nói tiếng Anh:** 15 phút/ngày không màn hình; bán qua trung tâm — {{ a.eng_price|money(2) }} + thuê bao

## Bản đồ vùng đất

| Vùng | Phán quyết |
|---|---|
| Nền tảng bộ não B2B | Lõi giá trị |
| Người già "Con cháu" | Mũi nhọn dài hạn |
| Luyện nói tiếng Anh | Mũi nhọn ngắn hạn |
| Giáo dục AI, dịch vụ dữ liệu | Dòng tiền sớm |
| CLB, nhượng quyền | Năm 4+ |
| Nhập robot về bán | Loại — đua giá |

## Lợi nhuận theo mảng ({{ b.last.year }}, cơ sở)

{% for g in b.segments.values() %}
- {{ g.name }}: doanh thu {{ g.last.revenue|ty }} · đóng góp {{ g.last.contribution|ty }}
{% endfor %}

## Tài chính ({{ meta.unit_label }}, kịch bản cơ sở)

{% with scenario = "base" %}{% include "partials/pnl.md.j2" %}{% endwith %}


## Ba kịch bản

{% for k, f in fin.items() %}
- **{{ k }}**: doanh thu {{ f.last.year }} {{ f.last.revenue|ty }} · EBITDA {{ f.last.ebitda|ty }} · hoà vốn {{ f.metrics.breakeven_year or "chưa" }} · tiền thấp nhất {{ f.metrics.min_cash|ty }}
{% endfor %}

## Lộ trình & cửa ải

- **Giai đoạn 0** ({{ a.phase0_budget|money(0) }}, 8–12 tuần): 4 thí nghiệm, tiêu chí qua/không qua đặt trước
- **Cửa ải 1:** bộ não khả thi + người dùng còn dùng sau 4–6 tuần + có người trả tiền
- **Giai đoạn 1** ({{ a.phase1_budget|ty }}): ra mắt, 2 thương hiệu nền tảng
- **Cửa ải 2:** giữ chân thuê bao 90 ngày, đơn vị kinh tế dương
- **Giai đoạn 2** ({{ a.phase2_budget|ty }}): mở rộng ĐNA, B2B, CLB flagship

## Rủi ro lớn nhất & cách xử lý

- Hết hứng thú → đo ngay ở giai đoạn 0
- An toàn trẻ em → bộ lọc 2 lớp, red-team
- Luật dữ liệu → server VN, luật sư từ đầu
- Chi phí AI → tự host, giới hạn sử dụng

## Đề xuất

- Bắt đầu bằng **{{ a.phase0_budget|money(0) }}** cho giai đoạn kiểm chứng
- Vốn tiếp theo chỉ mở khi có số liệu thật
- Công ty cổ phần; đội kỹ thuật nhận cổ phần theo vesting

{% if draft %}
## Lưu ý

{% include "partials/draft.md.j2" %}
{% endif %}
