# Rủi ro, phản biện & khi nào KHÔNG nên đầu tư

## Sổ rủi ro

| Rủi ro | Khả năng | Tác động | Giảm thiểu |
|---|---|---|---|
| Người dùng hết hứng thú sau vài tuần (bài học TQ: trả hàng khoảng {{ a.fact_return_rate|pct }}) {{ cite('ev-36kr-returns') }} | Cao | Rất cao | Chọn nhóm có nỗi đau lặp lại hằng ngày (người già cô đơn, luyện nói); trí nhớ + nội dung mới; đo ở giai đoạn 0 trước khi sản xuất lớn |
| Sự cố an toàn nội dung với trẻ em/người già {{ cite('ev-folotoy') }} | Trung bình | Rất cao (thương hiệu, pháp lý) | Bộ lọc 2 lớp, red-team định kỳ, nhật ký, phụ huynh kiểm soát |
| Vi phạm luật dữ liệu cá nhân / luật AI {{ cite('ev-pdp-law', 'ev-ai-law') }} | Trung bình | Cao | Server tại VN, ẩn danh trước khi gọi API nước ngoài, luật sư từ đầu |
| Chi phí AI cao hơn giá thuê bao | Trung bình | Cao | Tự host ASR/TTS, mô hình nhỏ, giới hạn sử dụng; lớp chuyển nhà cung cấp |
| Viettel/FPT hoặc nền tảng TQ làm cùng lớp bộ não {{ cite('ev-viettel-iflytek') }} | Trung bình | Cao | Tập trung vào tính cách + an toàn + nội dung cho 2 nhóm cụ thể; hợp tác thay vì đối đầu ở tầng giọng nói |
| Công ty dừng hoạt động làm thiết bị "chết" (Moxie) {{ cite('ev-moxie') }} | Thấp | Cao (uy tín) | Cam kết chế độ hoạt động tối thiểu khi mất kết nối; điều khoản chuyển giao server |
| Mất C/O form E, sai mã HS | Thấp | Trung bình | Xác định trước mã số; điều khoản xuất xứ trong hợp đồng OEM |
| Đội nhỏ, ôm quá nhiều mảng | Cao | Cao | Giai đoạn 0 chọn tối đa 2 sản phẩm; CLB và nhượng quyền để sau |

## 10 câu hỏi khó nhất nhà đầu tư sẽ hỏi

1. **"Người TQ làm rẻ hơn, sao ta thắng?"** — Ta không thắng ở vỏ máy; ta mua vỏ máy của họ. Ta thắng ở tiếng Việt, an toàn, tuân thủ luật VN, và biến họ thành khách hàng nền tảng.
2. **"Viettel làm thì sao?"** — Viettel làm hạ tầng giọng nói; ta làm tính cách + nội dung + an toàn cho người già/trẻ em. Họ có thể là nhà cung cấp, đối tác kênh, hoặc người mua lại.
3. **"Người già có dùng công nghệ không?"** — Thiết bị không màn hình, chỉ cần nói; con cái cài đặt. Hàn Quốc đã chứng minh qua chương trình công {{ cite('ev-hyodol') }}. Ta kiểm chứng bằng thí nghiệm C trước khi bỏ tiền lớn.
4. **"Hết hứng thú thì sao?"** — Đó là rủi ro số 1; vì vậy cửa ải đầu tiên đo đúng chỉ số đó.
5. **"Sao không làm app cho rẻ?"** — Phụ huynh không muốn thêm màn hình; người già không dùng app tốt. Thiết bị là kênh để AI vào được những chỗ app không vào được.
6. **"Mất bao lâu có lãi?"** — Kịch bản cơ sở hoà vốn EBITDA năm {{ fin.base.metrics.breakeven_year }}; kịch bản xấu năm {{ fin.bear.metrics.breakeven_year or "—" }} và cần thêm vốn.
7. **"Tiền của tôi rủi ro tối đa bao nhiêu?"** — Giai đoạn 0 là {{ a.phase0_budget|money(0) }}; giai đoạn sau chỉ mở khi có số liệu.
8. **"Đội có làm được không?"** — Kỹ thuật + tiếng Trung + nguồn hàng là đúng bộ kỹ năng cho mô hình này; thiếu hụt là marketing/kênh người già → tuyển hoặc đối tác.
9. **"Thoát vốn bằng cách nào?"** — Bán cho nhà mạng/công ty công nghệ lớn cần lớp AI tiếng Việt cho thiết bị, hoặc gọi vốn quỹ ở giai đoạn 2.
10. **"Vì sao bây giờ?"** — Luật dữ liệu và luật AI mới (2026), AI vào trường học (2026-27), thiết bị TQ đang tràn vào VN, chi phí AI vừa đủ rẻ.

## Khi nào KHÔNG nên đầu tư

- Nếu giai đoạn 0 cho thấy người dùng bỏ thiết bị trước tuần thứ 6 ở **cả** sản phẩm người già lẫn tiếng Anh.
- Nếu chi phí AI thực tế không xuống được dưới giá thuê bao mà người mua chịu trả.
- Nếu đội không dành toàn thời gian ít nhất cho giai đoạn 0–1.
- Nếu mục tiêu của nhà đầu tư là "nhập hàng bán lãi nhanh" — đây không phải mô hình đó.
