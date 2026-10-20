---
title: "{{ p.name }} — Báo cáo khai phá lĩnh vực & kế hoạch"
subtitle: "Phiên bản {{ version }} · {{ today }}"
---
{% set b = fin.base %}

{% include "partials/draft.md.j2" %}

# Tóm tắt điều hành

## Một câu

**Xây "bộ não AI nói tiếng Việt" cho các thiết bị nhỏ biết nghe, nói, nhớ và an toàn; chứng minh nó bằng 2 sản phẩm của chính mình (bạn đồng hành cho người già, bạn luyện nói tiếng Anh cho trẻ); rồi cấp phép bộ não đó cho mọi hãng phần cứng muốn bán vào Việt Nam và Đông Nam Á.**

## Vì sao đây là vùng đất màu mỡ ít người thấy

1. **Phần cứng đã thành hàng hoá, bộ não thì chưa có cho tiếng Việt.** Giá về kho một thiết bị giọng nói cơ bản chỉ khoảng {{ a.fact_landed_low }} USD {{ cite('ev-alibaba-aipets') }}; firmware mã nguồn mở gần như miễn phí {{ cite('ev-xiaozhi') }}. Giá trị dịch chuyển sang lớp ngôn ngữ, tính cách, trí nhớ, an toàn, nội dung — và **chưa ai làm chủ lớp này bằng tiếng Việt ở cấp tiêu dùng** (research/06, research/07).
2. **Trung Quốc đã chứng minh mô hình.** Thị trường AI toy TQ đạt khoảng {{ a.fact_cn_aitoy_2025 }} tỷ NDT năm 2025 {{ cite('ev-caixin-aitoy') }}, dự báo tới {{ a.fact_cn_aitoy_2030 }} tỷ NDT năm 2030 {{ cite('ev-mittr-aitoy') }}, với hơn {{ a.fact_cn_aitoy_firms|num }} công ty. Một nền tảng "bộ não" (Doubao) đã chạy trên hơn {{ a.fact_doubao_devices|num }} thiết bị {{ cite('ev-36kr-ropet') }}.
3. **Độ trễ 2–4 năm đang diễn ra trước mắt.** Robot hút bụi — sản phẩm đã bão hoà ở TQ — vừa tăng {{ a.fact_vn_vacuum_growth|pct }} trong một năm ở Việt Nam, lên {{ a.fact_vn_vacuum }} triệu USD, và hãng TQ chiếm gần hết {{ cite('ev-vacuum-vn') }}. Làn sóng thiết bị AI biết nói sẽ đi đúng con đường đó; câu hỏi chỉ là ai cung cấp "bộ não tiếng Việt" cho chúng.
4. **Ba lực cấu trúc không phụ thuộc trào lưu.** Già hoá nhanh: {{ a.fact_vn_60plus }} triệu người 60+ hôm nay, {{ a.fact_vn_60plus_2050 }} triệu năm 2050, thành xã hội già quanh năm {{ a.fact_vn_aged_year }} {{ cite('ev-unfpa-ageing') }}. Chính sách giáo dục: AI vào toàn bộ trường phổ thông từ năm học 2026-27 {{ cite('ev-qd2422') }}, tiếng Anh thành ngôn ngữ thứ hai tới 2035 {{ cite('ev-qd2371') }}. Luật: dữ liệu cá nhân (đặc biệt của trẻ em) và AI bị siết, ưu tiên xử lý trong nước {{ cite('ev-pdp-law', 'ev-ai-law') }} — **đây là hào bảo vệ cho người làm bộ não đặt server tại Việt Nam**.

## Điều chúng tôi KHÔNG làm (và vì sao)

- **Không lấy "nhập robot Trung Quốc về bán" làm mô hình.** Ở TQ đã có chiến tranh giá, tỷ lệ trả hàng do hết hứng thú khoảng {{ a.fact_return_rate|pct }} {{ cite('ev-36kr-returns') }}, và phần lớn nhà sáng lập mảng này đã bỏ cuộc {{ cite('ev-36kr-margin') }}. Ai cũng nhập được — đó không phải lợi thế.
- **Không mở chuỗi CLB trước khi có lõi.** CLB có chi phí cố định cao; nếu doanh thu chỉ đạt khoảng 2/3 kỳ vọng thì gần như không hoàn vốn (research/05). CLB là tầng mở rộng thương hiệu ở năm thứ tư.

## Con số chính (kịch bản cơ sở — ước tính, cần kiểm chứng)

| | {{ b.years[0].year }} | {{ b.years[2].year }} | {{ b.last.year }} |
|---|---:|---:|---:|
| Doanh thu | {{ b.years[0].revenue|ty }} | {{ b.years[2].revenue|ty }} | {{ b.last.revenue|ty }} |
| EBITDA | {{ b.years[0].ebitda|ty }} | {{ b.years[2].ebitda|ty }} | {{ b.last.ebitda|ty }} |

Hoà vốn EBITDA năm {{ b.metrics.breakeven_year }}. Tổng vốn cần cho 5 năm khoảng {{ b.metrics.raise_amount|ty }}, **giải ngân theo cửa ải**, khởi đầu chỉ {{ a.phase0_budget|money(0) }} cho giai đoạn kiểm chứng. Thuê bao (tiền lặp lại hằng tháng) là dòng lợi nhuận tăng nhanh nhất, chiếm gần một nửa lợi nhuận đóng góp năm cuối — đó là thứ làm doanh nghiệp này có giá trị, không phải việc bán máy.

## Phán quyết thẳng

**Lĩnh vực: đáng khai phá.** Lực đẩy có thật, có bằng chứng ở TQ/Hàn/Mỹ, khoảng trống tiếng Việt có thật, thời điểm (luật mới + chính sách giáo dục + độ trễ thị trường) đang mở.

**Dự án: đáng đầu tư ở giai đoạn 0, CHƯA đáng đầu tư lớn.** Mọi con số kinh doanh trong báo cáo này là ước tính. Ba giả định quyết định sống chết — (1) người dùng còn dùng sau 6 tuần, (2) người mua chịu trả thuê bao, (3) nhận dạng giọng tiếng Việt của người già/trẻ em đủ tốt với chi phí AI đủ rẻ — đều kiểm chứng được trong 8–12 tuần với ngân sách {{ a.phase0_budget|money(0) }}. Qua được cửa ải đó, đây là một cơ hội lớn; không qua, ta dừng với thiệt hại nhỏ và bài học rõ ràng.
