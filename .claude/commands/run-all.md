---
description: Chạy toàn bộ các stage còn todo của 1 dự án theo thứ tự phụ thuộc
argument-hint: <slug>
---
Chạy pipeline cho dự án $ARGUMENTS.

1. `python gen.py status $ARGUMENTS` để xem stage nào còn todo.
2. Chạy lần lượt theo `depends` trong `pipeline/stages.yaml`. Các stage cùng đủ điều kiện và ghi
   file khác nhau (vd 02-market, 04-customer, 05-product-supply) có thể giao cho subagent nghiên cứu
   song song — subagent chỉ trả về dữ liệu + nguồn; bạn là người duy nhất ghi vào SSOT để tránh lệch.
3. Mỗi stage: theo `/run-stage`. Commit sau mỗi stage.
4. Cuối cùng: build, check, gửi cho Ryan các file trong `projects/<slug>/build/` và tóm tắt:
   số giả định verified/estimate/placeholder, các human_gate còn mở, 5 câu hỏi khó nhất nhà đầu tư sẽ hỏi.
