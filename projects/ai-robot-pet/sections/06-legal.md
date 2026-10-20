# Pháp lý, thuế & ưu đãi (chi tiết research/03)

## Thuế nhập khẩu — giả thuyết ban đầu cần sửa

- Ý tưởng gốc cho rằng robot "dùng cho giáo dục" sẽ được ưu đãi thuế. **Không đúng** với doanh nghiệp thương mại: miễn thuế cho hàng phục vụ giáo dục chỉ áp cho trường/viện nhập trực tiếp (research/03).
- **Nhưng không cần ưu đãi đó:** hàng có xuất xứ Trung Quốc với C/O form E theo ACFTA được **thuế nhập khẩu {{ a.fact_acfta_duty|pct }}** cho cả mã đồ chơi (9503) lẫn mã thiết bị điện tử {{ cite('ev-hs-9503') }}. Mất form E thì mã đồ chơi chịu thuế MFN {{ a.fact_mfn_toy_duty|pct }}.
- Mã HS chủ yếu quyết định VAT (đồ chơi trẻ em thấp hơn thiết bị điện tử) và quy chuẩn phải đáp ứng. **Việc cần làm:** xin xác định trước mã số cho từng sản phẩm.

## Hợp quy bắt buộc

- **Đồ chơi:** QCVN 3:2019/BKHCN — thử nghiệm ở phòng lab chỉ định, chứng nhận, dấu CR (research/03).
- **Vô tuyến:** theo Thông tư 29/2025/TT-BKHCN, Wi-Fi/Bluetooth công suất thấp (dưới 60 mW EIRP) nằm ngoài danh mục; cao hơn phải chứng nhận QCVN 54 {{ cite('ev-tt29-2025') }}. **Thiết kế: chọn module công suất thấp.**
- Pin: trách nhiệm tái chế (EPR) của nhà nhập khẩu.

## Dữ liệu & AI — rủi ro lớn nhất, cũng là hào bảo vệ

- **Luật Bảo vệ dữ liệu cá nhân 91/2025** (hiệu lực 01/01/2026): dữ liệu trẻ em từ 7 tuổi cần đồng ý của cả trẻ và cha mẹ; **gửi dữ liệu sang API nước ngoài là chuyển dữ liệu xuyên biên giới** — phải đánh giá tác động, nộp Bộ Công an; phạt tới phần trăm doanh thu {{ cite('ev-pdp-law') }}.
- **Luật Trí tuệ nhân tạo 134/2025** (hiệu lực 01/03/2026): quản lý theo rủi ro, gắn nhãn nội dung AI, có thời gian chuyển tiếp; AI cho trẻ em có thể bị xếp rủi ro cao {{ cite('ev-ai-law') }}.
- **Hàm ý chiến lược:** server tại Việt Nam, ẩn danh trước khi gọi mô hình nước ngoài, bộ lọc an toàn + nhật ký kiểm toán từ ngày đầu. Chi phí tuân thủ đã nằm trong model (dòng "Hợp quy & an toàn"). Hãng nước ngoài muốn bán vào VN sẽ cần đúng những thứ này — **đó là sản phẩm B2B của ta**.

## Ưu đãi có thật

- Doanh nghiệp nhỏ và vừa thành lập mới: **miễn thuế TNDN 3 năm**; khởi nghiệp sáng tạo được công nhận còn có ưu đãi dài hơn {{ cite('ev-nq198') }}. Sau đó thuế suất theo doanh thu {{ cite('ev-cit-law') }}. Model đã áp dụng.
- Luật Công nghiệp công nghệ số 71/2025 có hỗ trợ đầu tư cho sản phẩm công nghệ số và khởi nghiệp sáng tạo — mức cụ thể cần luật sư xác nhận (research/03).
- Nhà đầu tư vào khởi nghiệp sáng tạo được công nhận có thể được miễn thuế TNCN (Luật KH-CN & ĐMST 93/2025).

## Cấu trúc doanh nghiệp

- **Công ty cổ phần** để nhận nhiều nhà đầu tư.
- **"Góp vốn bằng công sức/lương" không hợp pháp** theo Luật Doanh nghiệp {{ cite('ev-sweat-equity') }}. Cách làm chuẩn: xem phần Cấu trúc vốn.

## Việc cần người thật làm

- Luật sư BVDLCN: thiết kế luồng đồng ý của phụ huynh, hồ sơ đánh giá tác động chuyển dữ liệu.
- Đại lý hải quan: xác định trước mã HS, quy trình form E.
- Lab thử nghiệm: báo giá QCVN 3 và kiểm tra module vô tuyến.
