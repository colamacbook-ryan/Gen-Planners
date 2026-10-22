---
title: "{{ p.name }}"
subtitle: "Hệ sinh thái AI Robot Pet Việt · v{{ version }}"
date: "{{ today }}"
---
{% set b = fin.base %}

## Robot pet AI đã là ngành lớn ở Trung Quốc

- Thị trường AI toy {{ a.fact_cn_aitoy_2025 }} tỷ NDT (2025) → tới {{ a.fact_cn_aitoy_2030 }} tỷ NDT (2030)
- Fuzozo: {{ a.fact_fuzozo_units|num }} máy, người dùng trò chuyện {{ a.fact_fuzozo_minutes }} phút/ngày
- {{ a.fact_fuzozo_female|pct }} người dùng cốt lõi là nữ trưởng thành → nhu cầu là **bạn đồng hành**
- Việt Nam: chưa có robot pet nào nói tiếng Việt, chưa có CLB robotics cho giới trẻ

## Điểm yếu của cả ngành, và cơ hội của ta

- Ở TQ, {{ a.fact_return_rate|pct }} AI plush bị trả lại vì chủ chán sau vài tuần
- Người giữ được người dùng thắng: Ropet giữ {{ a.fact_ropet_retention|pct }} sau 90 ngày
- **CLB, thi đấu, huấn luyện, nâng cấp = lý do để quay lại mỗi tuần**

## Giải pháp: hệ sinh thái 4 tầng

1. **Pet tháo rời não–thân**, thương hiệu riêng, não chạy server Việt Nam
2. **CLB robotics**: góc trải nghiệm → CLB flagship: chơi, F&B, thi đấu
3. **Học viện**: huấn luyện prompt, lập trình pet; gói giáo án cho trường
4. **Nhượng quyền** khi CLB đầu có lãi

## Sản phẩm

- Một não, nhiều thân: bánh xe, chó 4 chân, thú bông, đế để bàn
- Gói kỹ năng: bạn đồng hành · luyện tiếng Anh · chăm sóc ông bà · lập trình
- Bộ pet {{ a.pet_price|money(2) }} · gói kỹ năng {{ (a.brain_sub_price / 12 * 1000)|num }} nghìn đ/tháng
- Về kho khoảng {{ a.fact_landed_pet }} USD/bộ · thuế nhập khẩu {{ a.fact_acfta_duty|pct }} với form E

## Mỗi pet bán ra mở một dòng chi tiêu

- Thân mới, skin, phụ kiện · gói kỹ năng · khoá học · sửa chữa, nâng cấp · vé CLB
- Năm {{ b.last.year }}: phần lớn doanh thu đến từ hệ sinh thái, không phải bán máy

## Lợi nhuận theo mảng ({{ b.last.year }}, cơ sở)

{% for g in b.segments.values() %}
- {{ g.name }}: doanh thu {{ g.last.revenue|ty }} · đóng góp {{ g.last.contribution|ty }}
{% endfor %}

## Tài chính ({{ meta.unit_label }}, kịch bản cơ sở)

{% with scenario = "base" %}{% include "partials/pnl.md.j2" %}{% endwith %}


## Các kịch bản

{% for k, f in fin.items() %}
- **{{ k }}**: doanh thu {{ f.last.year }} {{ f.last.revenue|ty }} · EBITDA {{ f.last.ebitda|ty }} · hoà vốn {{ f.metrics.breakeven_year or "chưa" }}
{% endfor %}

## Lộ trình & cửa ải

- **Giai đoạn 0** ({{ a.phase0_budget|money(0) }}, 8–12 tuần): mẫu OEM, góc pop-up, workshop, đặt cọc
- **Giai đoạn 1** ({{ a.phase1_budget|ty }}): lô đầu, 3 góc trải nghiệm, học viện
- **Giai đoạn 2** ({{ a.phase2_budget|ty }}): CLB flagship, nhượng quyền

## Đề xuất góp vốn

- Bắt đầu bằng {{ a.phase0_budget|money(0) }} cho giai đoạn kiểm chứng
- Công ty cổ phần; bạn bè góp tiền, đội kỹ thuật nhận cổ phần theo vesting
- Vốn tiếp theo mở theo cửa ải

{% if draft %}
## Lưu ý

{% include "partials/draft.md.j2" %}
{% endif %}
