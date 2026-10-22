{% set m = fin.base.metrics %}
# Cấu trúc vốn — khung đề xuất (bàn chi tiết sau)

## Nhu cầu vốn theo giai đoạn

| Giai đoạn | Vốn | Mở khi |
|---|---:|---|
| 0 — Kiểm chứng | {{ a.phase0_budget|money(0) }} | Ngay |
| 1 — Ra mắt | {{ a.phase1_budget|ty }} | Qua cửa ải 1 |
| 2 — Mở rộng | {{ a.phase2_budget|ty }} | Qua cửa ải 2 (có thể gọi từ quỹ đầu tư khi đã có số liệu thật) |
| **Tổng** | **{{ m.raise_amount|ty }}** | |

## Nguyên tắc cho bạn bè đầu tư

1. **Góp theo cửa ải, không góp một lần.** Giai đoạn 0 nhỏ; rủi ro tối đa của nhà đầu tư ban đầu được giới hạn ở khoản đó.
2. **Công ty cổ phần.** Nhà đầu tư góp tiền nhận cổ phần; có thể dùng cổ phần ưu đãi.
3. **Đội kỹ thuật không thể "góp vốn bằng lương/công sức"** — luật không cho phép {{ cite('ev-sweat-equity') }}. Cách hợp pháp và phổ biến:
   - Nhà sáng lập mua cổ phần theo mệnh giá (số tiền nhỏ) và nhận thêm cổ phần theo **vesting** (ví dụ 4 năm, cliff 1 năm) ghi trong thoả thuận cổ đông; rời sớm thì công ty mua lại phần chưa vest.
   - Tài sản trí tuệ (mã nguồn, thiết kế) có thể góp bằng hiện vật sau khi định giá.
   - Quỹ ESOP cho nhân sự chủ chốt do ĐHĐCĐ thông qua.
   - Nhận lương thấp hơn thị trường được bù bằng cổ phần vesting — ghi rõ trong hợp đồng, không ghi "góp vốn bằng lương".
4. **Định giá giai đoạn 0** nên đơn giản (hoặc dùng thoả thuận chuyển đổi kiểu SAFE/khoản vay chuyển đổi theo luật VN) — định giá thật làm ở giai đoạn 1 khi đã có số liệu.

## Tham khảo (mô hình, không phải cam kết)

Với giả định định giá trước vốn {{ m.pre_money|ty }} cho toàn bộ {{ m.raise_amount|ty }}, nhà đầu tư nắm {{ m.investor_stake|pct }}; nếu doanh nghiệp đạt kế hoạch cơ sở và được định giá {{ a.exit_multiple }} lần EBITDA năm {{ fin.base.last.year }}, giá trị phần của nhà đầu tư khoảng {{ m.investor_moic|num(1) }} lần vốn góp. Kịch bản xấu: {{ fin.bear.metrics.investor_moic|num(1) }} lần. Các con số này chỉ để minh hoạ cấu trúc — định giá thật phụ thuộc kết quả giai đoạn 0–1.

## Việc cần người thật làm

Luật sư doanh nghiệp soạn điều lệ, thoả thuận cổ đông (vesting, mua lại, quyền nhà đầu tư) trước khi nhận tiền.
