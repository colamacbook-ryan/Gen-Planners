# Lộ trình khai phá & các cửa ải

Nguyên tắc: **mỗi giai đoạn chỉ mở khi cửa ải trước đã qua bằng số liệu thật.** Không qua thì dừng hoặc đổi hướng — thiệt hại được giới hạn bằng ngân sách của giai đoạn đó.

## Giai đoạn 0 — Kiểm chứng (8–12 tuần, {{ a.phase0_budget|money(0) }})

Bốn thí nghiệm chạy song song, mỗi thí nghiệm có tiêu chí qua/không qua đặt trước:

| Thí nghiệm | Làm gì | Ngân sách | Qua khi |
|---|---|---|---|
| A. Tiếng Anh | Landing page + quảng cáo đặt cọc trước; 20 mẫu cho 20 gia đình trong 4 tuần; chào white-label 3 trung tâm | {{ a.exp_a_budget|money(0) }} | ≥ {{ a.gate_eng_deposit|pct }} khách để cọc; ≥ {{ a.gate_eng_use|pct }} trẻ còn dùng ≥ nửa số ngày ở tuần 4 |
| B. Bộ não | Firmware + server tham chiếu; đo nhận dạng giọng người già/trẻ em 3 miền; red-team bộ lọc an toàn; chào 10 thương hiệu VN + 5 hãng Thâm Quyến | {{ a.exp_b_budget|money(0) }} | Tỷ lệ lỗi nhận dạng ≤ {{ a.gate_asr_wer|pct }}; chi phí AI ≤ {{ a.gate_cloud_cost }} nghìn đ/người/tháng; ≥ 2 thư ý định hoặc pilot trả phí |
| C. Người già | 15 máy, 6 tuần, gia đình con ở HCM/HN, bố mẹ ở tỉnh; đo số lượt trò chuyện, thang đo cô đơn | {{ a.exp_c_budget|money(0) }} | ≥ {{ a.gate_elder_use|pct }} bố mẹ còn dùng ở tuần 6; ≥ {{ a.gate_elder_pay|pct }} con cái sẵn lòng trả thuê bao |
| D. Giáo dục | Kit + giáo án 12 tiết thử với 2 trung tâm STEM tư | {{ a.exp_d_budget|money(0) }} | ≥ 1 trung tâm đặt mua |

Kèm: chuyến khảo sát Thâm Quyến, mẫu OEM, server thử nghiệm, tư vấn luật dữ liệu.

**Cửa ải 1 (quyết định đầu tư giai đoạn 1):** B qua (bộ não khả thi kỹ thuật và kinh tế) **và** ít nhất một trong A hoặc C qua. Nếu cả A và C trượt → dừng hoặc chuyển hướng sang chỉ làm dịch vụ dữ liệu + giáo dục.

## Giai đoạn 1 — Ra mắt (12 tháng, {{ a.phase1_budget|ty }})

- Lô OEM đầu tiên, hợp quy QCVN, ra mắt 1–2 sản phẩm đã qua cửa ải.
- Kênh: trung tâm tiếng Anh (white-label), TikTok Shop/Shopee, hội người cao tuổi, cộng đồng người Việt ở Nhật/Hàn (con cái ở nước ngoài).
- Nền tảng: 2 thương hiệu tích hợp đầu tiên.
- Dịch vụ dữ liệu: 1–2 hợp đồng để có dòng tiền.

**Cửa ải 2:** tỷ lệ giữ chân thuê bao sau 90 ngày đạt mục tiêu; chi phí có một khách hàng thấp hơn lợi nhuận gộp khách đó mang lại trong 12 tháng; ≥ 2 thương hiệu trả phí nền tảng.

## Giai đoạn 2 — Mở rộng (năm 2–5, {{ a.phase2_budget|ty }})

- Nền tảng: mở rộng thương hiệu, thêm ngôn ngữ ĐNA; hợp tác Viettel/FPT về giọng nói.
- Người già: kênh bảo hiểm/nhà mạng/chính quyền địa phương; Thái Lan.
- Giáo dục: theo chính sách AI trong trường.
- CLB flagship đầu tiên năm {{ fin.base.years[3].year }}; nhượng quyền chỉ khi CLB có lãi ổn định ≥ 1 năm.

## Ba câu hỏi phải trả lời trước khi làm gì lớn

1. **Người dùng có còn dùng sau 6 tuần?** (bài học Jibo/Anki/Moxie và tỷ lệ trả hàng ở TQ)
2. **Ai trả tiền đều đặn, bao nhiêu?** (con cái, phụ huynh, trung tâm, hãng thiết bị)
3. **Bộ não tiếng Việt có đủ tốt và đủ rẻ?** (giọng người già/trẻ em, chi phí AI mỗi tháng)
