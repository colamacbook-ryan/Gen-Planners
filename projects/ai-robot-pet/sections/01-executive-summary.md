---
title: "{{ p.name }} — Báo cáo khai phá & kế hoạch"
subtitle: "Phiên bản {{ version }} · {{ today }}"
---
{% set b = fin.base %}
{% set s = b.segments %}

{% include "partials/draft.md.j2" %}

# Tóm tắt điều hành

## Một câu

**Xây hệ sinh thái AI Robot Pet Việt: pet tháo rời não–thân mang thương hiệu riêng, bộ não chạy trên server Việt Nam; chuỗi CLB robotics để chơi, huấn luyện, thi đấu, nâng cấp; học viện dạy huấn luyện prompt và lập trình pet; rồi nhượng quyền cả mô hình.**

## Vì sao mô hình này đúng lúc

1. **Robot pet AI đã thành ngành lớn ở Trung Quốc.** Thị trường AI toy đạt khoảng {{ a.fact_cn_aitoy_2025 }} tỷ NDT năm 2025 {{ cite('ev-caixin-aitoy') }} và dự báo tới {{ a.fact_cn_aitoy_2030 }} tỷ NDT năm 2030 {{ cite('ev-mittr-aitoy') }}. Một sản phẩm giá đại chúng (Fuzozo) bán khoảng {{ a.fact_fuzozo_units|num }} máy, người dùng trò chuyện trung bình {{ a.fact_fuzozo_minutes }} phút/ngày {{ cite('ev-pedaily-fuzozo') }}.
2. **Nguồn hàng rẻ, thuế bằng 0.** Một bộ pet để bàn có màn hình và camera về kho khoảng {{ a.fact_landed_pet }} USD {{ cite('ev-alibaba-aipets') }}; hàng có C/O form E chịu thuế nhập khẩu {{ a.fact_acfta_duty|pct }} {{ cite('ev-hs-9503') }}.
3. **Điểm yếu chết người của robot pet là người dùng chán sau vài tuần** — tỷ lệ trả hàng ở TQ khoảng {{ a.fact_return_rate|pct }} {{ cite('ev-36kr-returns') }}. **CLB, thi đấu, huấn luyện, nâng cấp chính là lời giải**: chúng cho người dùng lý do quay lại mỗi tuần. Người giữ được người dùng thắng: Ropet giữ {{ a.fact_ropet_retention|pct }} người dùng sau 90 ngày {{ cite('ev-36kr-ropet') }}.
4. **Mô hình "sản phẩm + trải nghiệm + tuỳ biến" đã được chứng minh ở quy mô lớn.** Pop Mart có biên gộp {{ a.fact_popmart_margin|pct }} nhờ IP và cửa hàng trải nghiệm {{ cite('ev-popmart') }}; Build-A-Bear sống nhờ trải nghiệm tự làm và phụ kiện, có cả mạng lưới nhượng quyền.
5. **Việt Nam đang ở vạch xuất phát.** Hàng thiết bị thông minh TQ đang tràn vào (robot hút bụi +{{ a.fact_vn_vacuum_growth|pct }} một năm {{ cite('ev-vacuum-vn') }}), {{ a.fact_vn_ai_users|pct }} người dùng online đã dùng AI {{ cite('ev-decisionlab-ai') }}, AI vào mọi trường phổ thông từ 2026-27 {{ cite('ev-qd2422') }} — nhưng chưa có robot pet nào nói tiếng Việt, chưa có CLB robotics cho giới trẻ.

## Hệ sinh thái 4 tầng

| Tầng | Làm gì | Doanh thu {{ b.last.year }} | Đóng góp {{ b.last.year }} |
|---|---|---:|---:|
| 1. Pet tháo rời não–thân | OEM thương hiệu riêng, não chạy server VN, bán thêm thân, skin, gói kỹ năng | {{ (s.pet.last.revenue + s.acc.last.revenue + s.brain.last.revenue)|ty }} | {{ (s.pet.last.contribution + s.acc.last.contribution + s.brain.last.contribution)|ty }} |
| 2. CLB robotics | Góc trải nghiệm trước, CLB flagship sau: chơi, F&B, thi đấu | {{ s.club.last.revenue|ty }} | {{ s.club.last.contribution|ty }} |
| 3. Học viện & dịch vụ | Huấn luyện prompt, lập trình pet, gói giáo án cho trường; sửa chữa, nâng cấp | {{ (s.academy.last.revenue + s.service.last.revenue)|ty }} | {{ (s.academy.last.contribution + s.service.last.contribution)|ty }} |
| 4. Nhượng quyền | Phí ban đầu + phí theo doanh thu từ CLB đối tác | {{ s.franchise.last.revenue|ty }} | {{ s.franchise.last.contribution|ty }} |

Người già và luyện tiếng Anh không phải sản phẩm riêng mà là **gói kỹ năng tải vào não pet** — cùng một thiết bị phục vụ nhiều nhóm khách.

## Con số chính (kịch bản cơ sở — ước tính, cần kiểm chứng)

| | {{ b.years[0].year }} | {{ b.years[2].year }} | {{ b.last.year }} |
|---|---:|---:|---:|
| Doanh thu | {{ b.years[0].revenue|ty }} | {{ b.years[2].revenue|ty }} | {{ b.last.revenue|ty }} |
| EBITDA | {{ b.years[0].ebitda|ty }} | {{ b.years[2].ebitda|ty }} | {{ b.last.ebitda|ty }} |

Hoà vốn EBITDA năm {{ b.metrics.breakeven_year }}. Tổng vốn 5 năm khoảng {{ b.metrics.raise_amount|ty }}, **giải ngân theo cửa ải**, khởi đầu {{ a.phase0_budget|money(0) }} cho giai đoạn kiểm chứng.

## Phán quyết

**Đáng khai phá, đầu tư giai đoạn kiểm chứng trước.** Ý tưởng hệ sinh thái giải đúng điểm yếu lớn nhất của ngành robot pet (hết hứng thú) và có mô hình tham chiếu thành công. Ba điều phải chứng minh bằng số thật trong 8–12 tuần: (1) người trẻ chịu bỏ tiền mua pet giá khoảng {{ a.pet_price|money(2) }}, (2) góc trải nghiệm kéo được khách và khách quay lại, (3) bộ não tiếng Việt chạy ổn với chi phí AI thấp.
