# Quy tắc giao diện Gen Planner

Áp dụng cho `login.html`, `app.html`, `admin.html` (dùng chung `gp.css` + `gp.js`). Trình xem hồ sơ `studio/index.html` có
bộ token riêng cùng tên biến (`--core`, `--on-core`, …) để còn chạy độc lập.

## Nền tảng
1. **Màu chỉ từ token** trong `:root` của `gp.css`; không mã hex trong HTML hay `style=""`. Chữ trên nền màu dùng `--on-core`,
   `--on-bad`, `--on-ok` (đủ tương phản ở cả sáng lẫn tối).
2. **Khoảng cách** theo thang 4/8/12/16/24; `style=""` chỉ cho giá trị động (độ rộng thanh, %).
3. **Icon** chỉ qua `icon(tên)` (SVG nét, theo màu chữ). Không emoji, không trộn ký tự Unicode làm icon.

## Khung trang
4. Mọi trang dùng `topbar(tiêu đề, mô tả, nút góc phải, phần dưới)`; luôn có mô tả một dòng; nút hành động chính của trang ở góc phải.
5. Tiêu đề thẻ là `h2`; `.k` chỉ làm nhãn nhỏ phía trên (eyebrow) hoặc nhãn KPI.
6. Trang nhiều nhóm thiết lập dùng `.settings` + `.subnav` (cả Cài đặt người dùng lẫn Cài đặt hệ thống).

## Thành phần
7. Nút: `pri` (tối đa một nút chính mỗi khu vực) · mặc định · `ghost` · `ghost danger` cho thao tác trong dòng; nền đỏ chỉ cho nút xác nhận xoá.
   Trong bảng/thẻ dùng `.sm`. Nhãn tiếng Việt viết hoa chữ đầu: "Xem log", "Sao chép", "Đóng".
8. Mọi trạng thái hiển thị qua `pill(mã)` với nhãn trong `STATUS` (gp.js) — không tự viết `<span class="pill">…`.
9. Bảng: thao tác ở `td.actions` (canh phải), số ở `.num`, bảng nằm trong `.scroll-x`; danh sách rỗng dùng `emptyRow(cột, câu, nút?)`.
10. Banner: `.banner` + `info | warn | bad | ok`. Thông báo toàn hệ thống là `globalBanner()` (tự có trong `topbar`).
11. Overlay (hộp thoại, ngăn kéo, menu, modal) đóng bằng Esc, bấm ra ngoài, và tự đóng khi chuyển trang (`closeOverlays`).

## Trạng thái
12. Đang tải: `loading()` trong vùng sẽ hiện dữ liệu; nút đang xử lý thì `disabled` + nhãn "Đang …".
13. Rỗng: một câu nói rõ tình trạng + một hành động tiếp theo.
14. Lỗi: lỗi form → `.err` ngay dưới form; lỗi thao tác → `toast`; lỗi tải trang → `loadError(câu, "hàm thử lại()")`.
    Lỗi không được bắt riêng vẫn hiện toast nhờ bộ bắt `unhandledrejection` trong gp.js.
15. Nút/ô bị khoá phải có một dòng giải thích vì sao.

## Nội dung
16. Số và ngày chỉ qua `fmt`, `fmtInt`, `fmtCompact`, `fmtUSD`, `fmtDate`, `fmtDay`, `when` (tương đối + giờ chính xác khi rê chuột).
    Số thập phân hiển thị và nhập bằng dấu phẩy.
17. Thuật ngữ dùng chung: **Plan** (chạy Plan), **lượt chạy**, **chủ hệ thống (owner)**, **admin**, **tài khoản agent**,
    **nhà cung cấp** (AI), **hồ sơ**, **giả định**, **điểm chốt**. Tên loại agent và nguồn chi phí lấy từ `ENGINE`, `BILL`, `ROLE`.
18. Kiểm tra mỗi màn ở 1440px sáng/tối và 390px: không cuộn ngang, không cột bị bóp còn một chữ mỗi dòng.
