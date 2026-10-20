---
description: Tạo dự án mới từ tên + mô tả ý tưởng, rồi chạy toàn bộ pipeline
argument-hint: <slug> <mô tả ý tưởng...>
---
Tạo dự án mới. Đối số: $ARGUMENTS (từ đầu tiên là slug, phần còn lại là mô tả ý tưởng).

1. Ghi phần mô tả ý tưởng ra file tạm, chạy `python gen.py new <slug> --name "<tên ngắn gọn bạn đặt>" --idea-file <file tạm>`.
2. Commit `[<slug>] init`.
3. Thực hiện đúng quy trình của `/run-all <slug>`.
