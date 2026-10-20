# R6 — Bản đồ use-case & khoảng trống ở Việt Nam

Thu thập 2026-10. [EST] = ước tính. Một số nguồn thứ cấp (aggregator/công ty tự công bố).
**Không tìm thấy sản phẩm/nền tảng AI đồ chơi/bạn đồng hành nói tiếng Việt nào do VN làm.**

## Why now
- Linh kiện trợ lý giọng nói ESP32-S3 (mic, amply, màn nhỏ) < 60 RMB (~$8) — smzdm.com/p/a6zw223g
- xiaozhi-esp32 MIT, v2.2.6 (19/04/2026)
- TQ: 50+ vòng gọi vốn từ 2025, tổng > ¥20 tỷ; > 1 tr thiết bị kết nối Doubao (06/2025); JD JoyInside > 40 thương hiệu (01/2026) — https://eu.36kr.com/en/p/3769249595835142 (16/04/2026)
- Chi phí AI dùng nhiều (20 phút/ngày) với model realtime mini ≈ $10/tháng → quá cao cho đại chúng; pipeline rẻ (ASR → model nhỏ → TTS, Doubao/Qwen) có thể < $2/tháng [EST, cần test]. **Chi phí sử dụng là ràng buộc thiết kế chính.**

## Đánh giá từng mảng
| Mảng | Nỗi đau | Sẵn lòng trả | Khoảng trống | Why now | Điểm |
|---|---|---|---|---|---|
| D1 Luyện nói tiếng Anh cho trẻ | Cao | Cao: phụ huynh đã chi 2,1–4,5 tr/tháng cho tiếng Anh | Luyện nói hằng ngày tại nhà, không màn hình | AI giọng nói rẻ | **4** |
| D7 "Bộ não AI tiếng Việt" cấp phép cho hãng khác | Trung bình (B2B) | Trung bình | Chưa có nền tảng tiếng Việt | Mô hình TQ đã chứng minh; Luật BVDLCN 91/2025 | **4** |
| D3 Bạn học thay màn hình | Trung bình–cao | Trung bình | Tiếng Việt + an toàn | Phản ứng với thời gian dùng màn hình | 3,5 |
| D2 Người cao tuổi | Cao/người, số người ít | Con cái ở thành phố trả | Bạn trò chuyện tiếng Việt | Già hoá | 3 (lên 4 vào 2030) |
| D4 Trường học | Trung bình | Thấp–trung bình | Kit + giáo án tiếng Việt | Chương trình AI toàn quốc 2026-27 | 3 |
| D5 Gen Z sưu tầm | Thấp–trung bình | Mua theo cảm hứng | Sở hữu nhân vật | 35% Gen Z VN dùng AI làm người tâm sự | 2,5 |
| D6 B2B lễ tân/quà tặng | Thấp | Theo dự án | Host đa ngôn ngữ rẻ | — | 2,5 |

### Bằng chứng chính
- **D1**: khảo sát 2026 (>1.200 phụ huynh có con 5–15 tuổi, 5 thành phố): 87% coi tiếng Anh thiết yếu; chi 2,1–4,5 tr/tháng; 53% chê chương trình cao cấp thiếu cá nhân hoá; **72% không chấp nhận học hoàn toàn online** — https://news.tuoitre.vn/ (103260328123950931, 28/03/2026). Học tiếng Anh số ~$43,1M (2025) → $123M (2034) (IMARC). ELSA ~5 tr user VN (thị trường lớn nhất). VUS/ILA ~7 tr+/khoá (nguồn không chính thức).
- **D2**: 60+ tăng ~560k người/năm; chỉ số già hoá 60,2 (vietnamnet 09/01/2025). 16,4% người 80+ sống một mình (2014). Di cư nội địa 3,8 tr người 2019–24 (NSO). ElliQ (New York, 800+ user): giảm cô đơn 95% (tự báo cáo, không nhóm đối chứng) — aging.ny.gov 01/08/2023. Hyodol (Hàn): >12.000 máy qua chương trình phúc lợi công (11/2025); thử nghiệm 69 người/6 tuần giảm trầm cảm. Không tìm thấy sản phẩm trò chuyện tiếng Việt cho người già.
- **D3**: trẻ 11–14 ở HCM dùng màn hình TB 2,2 giờ/ngày; 53,8% ≥2 giờ. FoloToy bị thu hồi. Luật BVDLCN 91/2025/QH15 hiệu lực 01/01/2026, bảo vệ thêm dữ liệu trẻ em.
- **D4**: QĐ 3439 (thí điểm), QĐ 2422 (toàn quốc, 12 tiết/lớp/năm); dự thảo thông tư STEM: danh mục thiết bị chỉ mang tính hướng dẫn, không bắt buộc mua sắm (vietnamplus 2026). VEX quốc gia 2025: 1.000+ HS, 105 đội.
- **D5**: Kaspersky 03/2026: 35% Gen Z VN dùng AI làm người tâm sự. Pop Mart pop-up HCM: 4.000+ khách những ngày đầu. Mặt dây AI blind-box ¥59 ở TQ.
- **D6**: robot SAHA (SHB, 2022), OPBA (Nam A Bank, 2019) — chỉ để trưng bày, không nhân rộng.
- **D7**: Kiki (Zalo), dịch vụ giọng nói Viettel là trợ lý/linh kiện chung, không phải nền tảng cho đồ chơi/bạn đồng hành.

## 3 khoảng trống tốt nhất + thí nghiệm (< 50 tr, 4–8 tuần)
**A. "Bạn luyện nói tiếng Anh"** (D1 + D3), bán qua trung tâm tiếng Anh. Thiết bị bông/để bàn, 15 phút/ngày theo trình độ sách giáo khoa, báo cáo tiến bộ cho phụ huynh.
- Test 1 (~15 tr): landing page + quảng cáo FB/TikTok, đặt trước 1,49 tr + 149k/tháng. Đạt nếu ≥ 3% khách để cọc và chi phí/lead < 50k [EST].
- Test 2 (~30 tr): 20 mẫu xiaozhi cho 20 gia đình trong 4 tuần. Đo tỷ lệ còn dùng ở tuần 4 (mục tiêu ≥ một nửa số ngày), đánh giá của phụ huynh, ý định trả tiền.
- Test 3: chào bản white-label cho 3 trung tâm tiếng Anh tầm trung.

**B. Bộ não AI tiếng Việt** (D7) cho các thương hiệu đồ chơi/quà tặng.
- Test (~35 tr): firmware + server tham chiếu trên xiaozhi; đo nhận dạng giọng trẻ em/người già theo vùng miền; red-team bộ lọc an toàn theo kịch bản kiểu PIRG; chào 10 thương hiệu VN + 5 hãng Thâm Quyến (bằng tiếng Trung).
- Đạt nếu: ≥ 2 pilot trả phí/LOI với giá mỗi thiết bị/tháng đủ bù chi phí AI.

**C. "Gọi bà"** (D2): loa trò chuyện hằng ngày bằng tiếng Việt với bố mẹ ở quê, nhắc uống thuốc, gửi con cái bản tóm tắt tâm trạng/hoạt động.
- Test (~40 tr): 15 máy, 6 tuần, gia đình có con ở HCM/HN và bố mẹ ở tỉnh. Đo số lượt trò chuyện/ngày (ElliQ ~30), thang đo cô đơn trước/sau, ý định trả 200–300k/tháng.
- Kênh thứ hai: 2 viện dưỡng lão, Hội Người cao tuổi.
- Đạt nếu: ≥ 60% bố mẹ còn dùng ở tuần 6 và ≥ 40% con cái sẵn lòng trả.

**Thêm (D4)**: pilot kit "robot giọng nói AI" + giáo án với 2 trung tâm STEM tư, bám chương trình 12 tiết — cách rẻ nhất để có doanh thu sớm.

## Cần kiểm chứng thêm
Giá Hyodol; giá realtime voice Volcano Engine; doanh thu/giá ELSA VN; học phí VUS/ILA 2025; giá Loona/Emo ở VN; số người già bị con cái di cư để lại.
