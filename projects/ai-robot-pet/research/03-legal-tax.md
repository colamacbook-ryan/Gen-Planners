# R3 — Pháp lý, thuế, hợp quy, dữ liệu, ưu đãi (VN, 2026-10-20)

[V] = đã xác nhận ở văn bản gốc/nhiều nguồn khớp nhau; [U] = nguồn thứ cấp/chưa đọc được bản gốc → coi là estimate. Một số cổng văn bản trả 403.

## 1. Mã HS & thuế
Văn bản: biểu thuế MFN NĐ 26/2023 (sửa bởi NĐ 21/2025, 73/2025, 199/2025, 72/2026, 201/2026 — không đụng chương 84/85/90/95) [V]; ACFTA NĐ 118/2022 (2022–2027, C/O form E) [V]; VAT Luật 48/2024: đồ chơi trẻ em, mô hình dạy học 5% [V]; giảm 10% → 8% tới 31/12/2026 (NQ 204/2025, NĐ 174/2025) [V]; hàng CNTT không được giảm [U].

| HS | Khi nào | MFN | ACFTA (form E) | VAT |
|---|---|---|---|---|
| 9503.00.99 / 9503.00.60 | robot pet bán như đồ chơi | 20% | 0% | 5% |
| 9503.00.80 | thiết bị giáo dục điện tử cầm tay cho trẻ | 20% | 0% | 5% |
| 8543.70.90 | thiết bị điện tử không phải đồ chơi | 0% | 0% | 10% |
| 8471.50.90 | bo mạch xử lý trong kit | 0% | 0% | 10% |
| 8517.62.99 | module Wi-Fi/BT rời | 0% | 0% | 10% |
| 9023.00.00 | thiết bị trình diễn "không dùng cho mục đích khác" | 0% | 0% | 8% (5% nếu được coi là mô hình dạy học) |
Nguồn: caselaw.vn/chi-tiet-ma-hs/{95030099, 95030080, 85437090, 84795000, 90230000, 84715090, 85176299}

**Kết luận:** có form E thì thuế NK = 0% với mọi mã → mã HS chủ yếu quyết định VAT (5% vs 10%) và hợp quy. Mất form E → mã 9503 chịu 20%. Xin xác định trước mã số (NĐ 08/2015 sửa đổi) [U].
**"Dùng cho giáo dục" KHÔNG làm giảm thuế NK** cho doanh nghiệp thương mại: miễn thuế theo Luật 107/2016 Đ16 chỉ cho trường học/viện nghiên cứu nhập trực tiếp và hàng trong nước chưa sản xuất được [U]. → Giả thuyết ưu đãi thuế trong ý tưởng gốc là sai, nhưng không quan trọng vì ACFTA đã 0%.

## 2. Hợp quy
- **Đồ chơi**: QCVN 3:2019/BKHCN (TT 09/2019) bắt buộc từ 01/01/2021; kiểm tra chất lượng khi nhập khẩu, thử nghiệm ở lab chỉ định, chứng nhận (tối đa 3 năm), dấu CR [V]. TT 04/2026 sửa đổi (chưa đọc được) [U]. Luật Chất lượng SP sửa đổi 78/2025 (hiệu lực 01/01/2026) chuyển sang phân loại rủi ro [V]. Lab ví dụ: Eurofins MTS. Chưa có biểu phí.
- **Vô tuyến**: TT 29/2025/TT-BKHCN (hiệu lực 31/12/2025, thay TT 02/2024) [V, đọc toàn văn https://www.qtsc.com.vn/uploads/files/2025/12/30/29_2025_TT-BKHCN_680684.pdf]: BT/2,4 GHz < 60 mW EIRP ngoài phạm vi; Wi-Fi 2,4 GHz 60–200 mW → chứng nhận + công bố QCVN 54:2020, công bố QCVN 112:2017 (EMC); 5 GHz ≥ 60 mW → QCVN 65:2021. → **Chọn module < 60 mW EIRP** hoặc dự trù chứng nhận.
- An toàn điện/EMC (QCVN 4:2009, 9:2012) — chưa rõ có áp cho sạc [U]. Pin: trách nhiệm tái chế EPR (NĐ 08/2022, sửa bởi NĐ 05/2025) [V].

## 3. Dữ liệu cá nhân
- **Luật BVDLCN 91/2025/QH15 + NĐ 356/2025** (hiệu lực 01/01/2026, thay NĐ 13/2023) [V].
- Trẻ em (Đ24): từ 7 tuổi cần đồng ý của cả trẻ và cha mẹ [V tiêu đề].
- **Dùng LLM API nước ngoài = chuyển dữ liệu xuyên biên giới** → đánh giá tác động, nộp Bộ Công an, cập nhật 6 tháng/lần khi thay đổi (Đ20) [V, GV Lawyers].
- Phạt: tới 5% doanh thu năm trước (vi phạm xuyên biên giới); 10 lần khoản thu (mua bán dữ liệu); tới 3 tỷ (khác) [V]. Xử lý bằng AI phải phân loại rủi ro (Đ30) [V].
- Miễn chỉ định cán bộ BVDL 5 năm cho DN nhỏ/khởi nghiệp, trừ khi xử lý dữ liệu nhạy cảm/số lượng lớn [V] — dữ liệu giọng/hình ảnh trẻ em có thể rơi vào ngoại lệ [U].
- Luật An ninh mạng 116/2025 (hiệu lực 01/07/2026): lưu dữ liệu người dùng tại VN; nghị định còn dự thảo [U].
→ **Server đặt tại VN là lợi thế pháp lý (và là moat với hãng nước ngoài).**

## 4. AI & ưu đãi
- **Luật Trí tuệ nhân tạo 134/2025/QH15** (hiệu lực 01/03/2026): quản lý theo rủi ro, gắn nhãn nội dung do AI tạo, 12–18 tháng chuyển tiếp; danh mục rủi ro cao còn dự thảo — robot bạn đồng hành cho trẻ có thể bị xếp vào [V/U].
- **Luật Công nghiệp công nghệ số 71/2025** (hiệu lực 01/01/2026) + NĐ 353/2025: Đ28 hỗ trợ đầu tư sản xuất/sản phẩm công nghệ số trọng điểm (HĐND tỉnh quyết hỗ trợ trực tiếp); Đ29 hỗ trợ khởi nghiệp sáng tạo; Đ44.2 dấu nhận diện sản phẩm do AI tạo [V]; nội dung ưu đãi thuế Đ28 chưa đọc được [U].
- **Thuế TNDN Luật 67/2025** (áp dụng kỳ tính thuế 2025): 15% nếu DT ≤ 3 tỷ; 17% nếu 3–50 tỷ; 20% chuẩn [V].
- **NQ 198/2025 Đ10 + NĐ 20/2026**: DNNVV mới thành lập **miễn TNDN 3 năm**; khởi nghiệp sáng tạo miễn 2 năm + giảm 50% 4 năm [V].
- Luật KH-CN & ĐMST 93/2025 + NĐ 268/2025: miễn thuế TNCN cho founder/nhà đầu tư vào khởi nghiệp sáng tạo được công nhận [V].
- Doanh nghiệp công nghệ cao: không thực tế với mô hình nhập khẩu + lắp ráp [U].

## 5. Doanh nghiệp
- CTCP (≥ 3 cổ đông, có cổ phần ưu đãi) là phương tiện chuẩn để nhận nhà đầu tư; TNHH tối đa 50 thành viên, khó thêm nhà đầu tư [U].
- **"Góp vốn bằng công sức" KHÔNG hợp pháp** (Luật DN Đ34 chỉ cho tiền, vàng, QSDĐ, sở hữu trí tuệ, công nghệ, bí quyết, tài sản định giá được) [V]. Cách làm phổ biến: founder góp tiền theo mệnh giá + thoả thuận cổ đông có vesting/mua lại phần chưa vest; góp IP/bí quyết bằng hiện vật có định giá (Đ36); ESOP do ĐHĐCĐ thông qua [U].
- Nhượng quyền: Luật Thương mại Đ284–291, NĐ 35/2006 (sửa NĐ 120/2011, 08/2018) — nhượng quyền trong nước không cần đăng ký; nhượng quyền ra nước ngoài đăng ký Bộ Công Thương [V]. Hệ thống phải hoạt động ≥ 1 năm; báo cáo hằng năm; cung cấp bản giới thiệu [U].

## 6. Câu lạc bộ
- F&B: giấy chứng nhận đủ điều kiện ATTP (Luật 55/2010 Đ34; NĐ 15/2018 vẫn áp dụng do NĐ 46/2026 bị tạm ngưng) [U].
- Thi đấu có thưởng: NĐ 81/2018 (sửa NĐ 128/2024, NĐ 239/2026 hiệu lực 26/06/2026) cho khuyến mại; thi kỹ năng thu phí chưa quy định rõ → tránh yếu tố may rủi, công bố thể lệ, khấu trừ thuế giải thưởng [U].
- Dạy học: NĐ 125/2024 Đ42 — trung tâm kỹ năng sống cần Sở GD&ĐT phê duyệt; STEM/robotics không được nêu tên → xin ý kiến Sở hoặc tổ chức dưới dạng hoạt động CLB/workshop [U].

## 5 rủi ro pháp lý lớn nhất
1. Dữ liệu trẻ em gửi sang LLM nước ngoài → đồng ý kép, host VN, ẩn danh trước khi gọi API, nộp hồ sơ đánh giá tác động, thuê luật sư BVDLCN.
2. Sai mã HS/mất form E → xác định trước mã số từng SKU; ghi form E vào hợp đồng OEM.
3. Hợp quy đồ chơi/vô tuyến → thử mẫu QCVN 3 trước khi đặt hàng; module < 60 mW.
4. Luật AI xếp AI cho trẻ em vào rủi ro cao → xây bộ lọc nội dung, nhãn AI, log ngay từ đầu.
5. Tranh chấp "góp vốn công sức" → CTCP góp tiền mệnh giá + vesting; định giá IP; ESOP.
