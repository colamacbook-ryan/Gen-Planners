{% set b = fin.base %}
# Mô hình kinh doanh: lợi nhuận lớn nhỏ ở từng mảng

## Sáu dòng tiền

| Mảng | Thu tiền thế nào | Giả định chính |
|---|---|---|
| Người già "Con cháu" | Bán máy + thuê bao tháng (con cái trả) | Máy {{ a.elder_price|money(2) }}; thuê bao {{ a.elder_sub_price|money(2) }}/năm; {{ a.elder_active|pct }} máy đã bán còn trả thuê bao |
| Bạn luyện nói tiếng Anh | Bán máy + thuê bao tháng; white-label qua trung tâm | Máy {{ a.eng_price|money(2) }}; thuê bao {{ a.eng_sub_price|money(2) }}/năm; {{ a.eng_active|pct }} còn trả thuê bao |
| Nền tảng bộ não (B2B) | Phí tích hợp mỗi thương hiệu + phí mỗi thiết bị | {{ a.brain_integration|money(0) }}/thương hiệu; {{ a.brain_fee|money(2) }}/thiết bị/năm |
| Giáo dục AI | Gói kit + giáo án theo năm cho trung tâm/trường tư | {{ a.edu_package|money(0) }}/khách/năm |
| Dịch vụ dữ liệu | Hợp đồng thu thập/gán nhãn dữ liệu giọng nói, video góc nhìn thứ nhất | Doanh thu dự án theo năm |
| CLB trải nghiệm | Vé, hội viên, khoá học, F&B, bán máy, sửa chữa | {{ a.club_rev|ty }}/CLB/năm, chi phí vận hành {{ a.club_opex|ty }}/CLB/năm |

## Lợi nhuận đóng góp theo mảng (kịch bản cơ sở)

Lợi nhuận đóng góp = doanh thu − giá vốn − chi phí trực tiếp của mảng (chưa trừ chi phí chung như đội lõi, marketing, hợp quy).

{% with scenario = "base" %}{% include "partials/segments.md.j2" %}{% endwith %}


## Đọc bảng này thế nào

{% set s = b.segments %}
- **Mảng lớn nhất là người già** ({{ s.elder.last.contribution|ty }} lợi nhuận đóng góp năm {{ b.last.year }}) vì **thuê bao tích luỹ**: mỗi máy bán ra năm trước vẫn trả tiền năm sau. Đây cũng là mảng nhạy nhất với giả định tỷ lệ còn trả thuê bao — cần kiểm chứng đầu tiên.
- **Tiếng Anh** đóng góp {{ s.english.last.contribution|ty }} năm cuối nhưng ra tiền sớm hơn và có kênh bán rẻ qua trung tâm.
- **Nền tảng bộ não** nhỏ trong 3 năm đầu ({{ s.brain.years[2].revenue|ty }} doanh thu năm {{ s.brain.years[2].year }}) nhưng tăng nhanh nhất (lên {{ s.brain.last.revenue|ty }} năm {{ b.last.year }}) và **có giá trị chiến lược lớn nhất**: nếu bỏ mảng này (kịch bản "no_brain"), EBITDA năm cuối giảm từ {{ b.last.ebitda|ty }} xuống {{ fin.no_brain.last.ebitda|ty }} — và quan trọng hơn, doanh nghiệp mất câu chuyện nền tảng quyết định định giá.
- **Giáo dục và dữ liệu** nhỏ nhưng ra tiền ngay năm đầu ({{ (s.edu.years[0].revenue + s.data.years[0].revenue)|ty(2) }}), nuôi đội ngũ và tạo dữ liệu giọng nói.
- **CLB** chỉ xuất hiện từ năm {{ b.years[3].year }}, đóng góp nhỏ so với vốn bỏ ra — vai trò là trưng bày thương hiệu, cộng đồng, nơi thử sản phẩm.

## Mảng nào mở rộng được

| Mảng | Cách mở rộng | Giới hạn |
|---|---|---|
| Nền tảng bộ não | Thêm thương hiệu, thêm ngôn ngữ ĐNA (Thái, Indonesia) — chi phí biên thấp | Cạnh tranh với nền tảng lớn |
| Người già | Kênh bảo hiểm, nhà mạng, chính quyền địa phương (mô hình Hàn Quốc); Thái Lan | Tốc độ chấp nhận của người già |
| Tiếng Anh | Chuỗi trung tâm, trường tư; nội dung theo chương trình quốc gia | Cạnh tranh nhiều, giá bị ép |
| Giáo dục AI | Theo chính sách AI trong trường | Ngân sách trường hạn chế |
| Dữ liệu | Theo nhu cầu lab quốc tế | Dịch vụ, không tích luỹ giá trị |
| CLB | Nhượng quyền sau khi CLB đầu có lãi ≥ 1 năm | Vốn lớn, rủi ro mặt bằng |

## Đơn vị kinh tế cần chứng minh

- **Biên gộp thiết bị** dương sau chi phí kênh — dự kiến đạt vì giá về kho thấp {{ cite('ev-alibaba-aipets') }}.
- **Chi phí AI/người dùng/tháng < giá thuê bao/tháng** với khoảng cách an toàn — mục tiêu dưới {{ a.gate_cloud_cost }} nghìn đ/tháng.
- **Tỷ lệ còn dùng sau 90 ngày** — người thắng ở TQ đạt mức {{ a.fact_ropet_retention|pct }} {{ cite('ev-36kr-ropet') }}; trung bình ngành tệ hơn nhiều.
