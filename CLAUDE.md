# Gen-Planners — luật vận hành cho Agent

Repo này biến 1 mô tả ý tưởng thành bộ hồ sơ gọi vốn (business plan .docx, pitch deck .pptx,
model tài chính .xlsx) theo một pipeline chuẩn. Nguyên tắc: **plan-as-code**.

## Luật SSOT (bất khả xâm phạm)

1. **Mọi con số chỉ sống ở `projects/<slug>/assumptions.yaml`.** Văn bản (`sections/*.md`, `deck.md`)
   chỉ tham chiếu bằng Jinja: `{{ a.price_main|money }}`, `{{ fin.base.last.revenue|money }}`,
   `{{ fin.base.metrics.breakeven_year }}`. `gen.py check` báo ERROR nếu thấy số gõ tay.
2. **Mọi nguồn chỉ sống ở `evidence.yaml`** và được trích bằng `{{ cite('ev-012') }}`.
   KHÔNG BAO GIỜ bịa nguồn, URL, báo giá, trích dẫn luật. Không tìm được → `status: estimate`
   + `note` giải thích cách ước tính. Chỉ đánh `verified` khi có nguồn ngoài đọc được/dữ liệu thật.
3. **`build/` là output** — không sửa tay, không commit. Muốn đổi gì → sửa SSOT rồi build lại.
4. Đổi 1 giả định = sửa đúng 1 dòng YAML → build → mọi tài liệu tự cập nhật. Không đi sửa từng file.
5. Mỗi stage chỉ sửa các file trong `writes` của stage đó (`pipeline/stages.yaml`).

## Playbook chuẩn

Đọc `pipeline/playbook.yaml` trước khi chạy dự án mới. Nguyên tắc số 1: **ý tưởng gốc và các điểm founder
đã chốt trong `brief.md` là trung tâm** — nghiên cứu để làm nó mạnh lên, không thay thế. Sau 12 stage, viết
`story.yaml`, `datasets.yaml`, `products.yaml`, tải ảnh/thumbnail clip đã kiểm chứng vào `media/`, rồi chạy
`python tools/export.py <slug>` để ra dữ liệu cho console (`studio/index.html`).

## Quy trình chạy 1 stage

1. Đọc `pipeline/stages.yaml` (checklist, depends, writes, human_gate) + `idea.md` + SSOT hiện tại.
2. Nghiên cứu bằng WebSearch/WebFetch; ưu tiên nguồn gốc (văn bản luật, số liệu thống kê,
   trang nhà sản xuất/sàn TMĐT) hơn blog. Ghi nguồn vào `evidence.yaml` ngay khi dùng.
3. Cập nhật `assumptions.yaml` (giá trị + status + confidence + source) rồi viết section.
4. `python gen.py build <slug> && python gen.py check <slug>` — phải 0 ERROR.
5. Đặt `stages.<id>: done` trong `project.yaml`; commit riêng cho stage:
   `[<slug>] <stage-id>: <tóm tắt>`. Git history = lịch sử phiên bản của hồ sơ.
6. Nếu stage có `human_gate`: liệt kê rõ việc Ryan cần làm ngoài đời (báo giá, phỏng vấn, luật sư)
   vào cuối section dưới tiêu đề "Việc cần người thật làm".

## Văn phong hồ sơ

- Viết cho nhà đầu tư có tiền nhưng không chuyên kỹ thuật: rõ ràng, có số, không thổi phồng.
- Tách bạch dữ liệu vs giả định vs kỳ vọng. Nêu rủi ro thẳng — nhà đầu tư tin người nói rõ rủi ro.
- Tiếng Việt, thuật ngữ chuyên ngành giữ tiếng Anh khi cần.

## Lệnh

```
python gen.py new <slug> --name "Tên" [--idea-file idea.md]
python gen.py build <slug>
python gen.py check <slug>
python gen.py status [<slug>]
```
Slash commands: `/new-project`, `/run-stage`, `/run-all`, `/change`.
