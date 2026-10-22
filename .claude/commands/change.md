---
description: Thay đổi giả định/nội dung của dự án và cập nhật toàn bộ hồ sơ
argument-hint: <slug> <thay đổi...>
---
Yêu cầu thay đổi: $ARGUMENTS

1. Xác định thay đổi chạm vào giả định nào trong `assumptions.yaml` hoặc section nào. Sửa tại SSOT, không sửa build.
2. Nếu thay đổi làm sai lập luận ở section khác (vd giá tăng → định vị so với đối thủ), cập nhật các câu chữ đó.
3. Build + check. Báo cáo diff các chỉ số chính trước/sau (doanh thu năm cuối, hòa vốn, tiền thấp nhất, MOIC).
4. Commit `[<slug>] change: <tóm tắt>`.
