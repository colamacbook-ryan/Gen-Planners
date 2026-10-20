# Gen-Planners

Máy sản xuất hồ sơ gọi vốn: **nhập tên + mô tả ý tưởng → Agent chạy pipeline 12 bước → ra business plan
(.docx), pitch deck (.pptx), model tài chính (.xlsx)** — tất cả sinh ra từ một nguồn số liệu duy nhất.

## Vì sao làm thế này

Vấn đề cũ: mỗi phần nhờ AI làm riêng → file rải rác, số mỗi nơi một kiểu, sửa 1 số phải mở 5 file.
Cách giải: coi kế hoạch kinh doanh như **code**.

```
idea.md ──► pipeline/stages.yaml (12 bước chuẩn, giống nhau cho mọi dự án)
                 │ Agent nghiên cứu, chỉ ghi vào SSOT
                 ▼
   assumptions.yaml  (mọi con số + trạng thái kiểm chứng)   evidence.yaml (mọi nguồn)
   sections/*.md, deck.md (văn bản, chỉ tham chiếu biến)
                 │ python gen.py build
                 ▼
   build/business-plan.docx · deck.pptx · financials.xlsx   (không bao giờ sửa tay)
```

- **Một số = một chỗ.** Đổi giá bán → sửa 1 dòng YAML → build → P&L, deck, Excel, tóm tắt cùng đổi.
- **`gen.py check` là cổng chất lượng:** chặn số gõ tay trong văn bản, nguồn không tồn tại,
  giả định "verified" mà không có nguồn, kịch bản base bị âm tiền.
- **Trung thực có cấu trúc:** mỗi giả định có `status` placeholder → estimate → verified. Còn giả định
  chưa verified thì mọi tài liệu tự gắn nhãn BẢN NHÁP.
- **Versioning = git.** Mỗi stage một commit; phiên bản hồ sơ in kèm git hash.

## Dùng

Trong Claude Code tại repo này:

```
/new-project ai-robot-pet <dán mô tả ý tưởng>     # tạo + chạy toàn bộ pipeline
/run-stage ai-robot-pet 06-legal-tax               # chạy lại 1 bước
/change ai-robot-pet giá nhập tăng 15%, gọi vốn 2 tỷ  # sửa và cập nhật toàn bộ
```

CLI trực tiếp: `pip install -r requirements.txt` (+ `pandoc` để ra docx/pptx), rồi
`python gen.py new|build|check|status`.

## Pipeline

`01-intake → 02-market → 03-competitors → 04-customer → 05-product-supply → 06-legal-tax →
07-business-model → 08-gtm → 09-financials → 10-deal → 11-risk → 12-pitch` — chi tiết checklist,
điều kiện hoàn thành và các **human gate** (việc AI không làm thay được: báo giá thật, phỏng vấn khách,
xác nhận mã HS, luật sư) trong `pipeline/stages.yaml`.
