# Tham chiếu model tài chính (assumptions.yaml → gen.py)

Mọi con số sống ở `assumptions:`; khối `model:` chỉ *trỏ* tới id giả định. Xem dự án mẫu đầy đủ:
`GET /api/samples` → `GET /api/projects/<slug-mẫu>/ssot/assumptions.yaml` (hoặc `projects/ai-robot-pet/` trong repo).

## Giả định
```yaml
meta: {currency: VND, unit_label: triệu đ, start_year: 2027, years: 5}
assumptions:
  price_cup: {label: Giá một ly, value: 0.055, unit: triệu đ, status: verified, confidence: medium, source: [ev-highlands-menu]}
  cups_year: {label: Ly bán/năm, value: [40000, 70000, 90000, 100000, 100000], unit: ly, status: estimate, confidence: low, source: [ev-000], note: cách ước tính…}
```
- `value`: một số (lặp mọi năm) hoặc list đúng `years` phần tử (thiếu thì lặp phần tử cuối). Tỷ lệ % ghi dạng thập phân (`0.2` = 20%).
- `status`: `placeholder` → `estimate` (có `note` cách ước tính) → `verified` (chỉ khi có nguồn ngoài trong `evidence.yaml`).
  `ev-000` = ước tính nội bộ, không phải nguồn.
- Ngày tháng trong `evidence.yaml`/`story.yaml`: nên đặt trong ngoặc kép (`date: "2026-03-19"`).

## Tham chiếu trong `model:` (ref)
| Cách viết | Nghĩa |
|---|---|
| `price_cup` | chuỗi theo năm của giả định đó |
| `[price_cup, cups_year]` | **tích** từng năm (giá × lượng, hoặc giá × tỷ lệ) |
| `cum:new_outlets` | **luỹ kế** (số điểm mở mới → số điểm đang chạy) |
| `120` hoặc `[0, 50, 80]` | hằng số / chuỗi viết thẳng (tránh — số nên sống ở `assumptions:`) |

```yaml
model:
  segments: {drinks: Đồ uống robot, kids: Lớp trẻ em}          # các tầng hệ sinh thái của founder
  revenue_streams:
    - {id: drinks, segment: drinks, price: price_cup, volume: [cups_per_outlet, cum:new_outlets], cogs_pct: cogs_drink_pct}
    - {id: kids, segment: kids, price: class_fee, volume: class_seats, cogs_pct: cogs_kids_pct, core: true}   # core: mảng lõi
  opex:
    - {name: Thuê mặt bằng, amount: [rent_month_x12, cum:new_outlets], segment: drinks}   # segment → tính vào lợi nhuận đóng góp của mảng
    - {name: Nhân sự văn phòng, amount: opex_hq}
  capex: capex_plan
  tax_rate: cit_rate              # số hoặc list theo năm (ví dụ miễn thuế 2 năm đầu: [0, 0, 0.1, 0.1, 0.2])
  funding: raise_amount           # vốn nhà đầu tư
  founder_capital: founder_capital   # (tuỳ chọn) vốn founder góp — cộng vào tiền đầu kỳ, không tính cổ phần nhà đầu tư
  pre_money: pre_money
  discount_rate: discount_rate
  exit_multiple: exit_multiple    # × EBITDA năm cuối
  scenarios:                      # hệ số nhân lên base
    base: {}
    bear: {volume_x: 0.6, price_x: 0.9, opex_x: 1.1}
    kids_weak: {stream_x: {kids: 0.6}}   # tầng yếu nhất chỉ đạt 60% — bắt buộc có một kịch bản như vậy
```

## Dùng trong văn bản (sections/*.md, deck.md) — Jinja, không gõ số tay
- Giả định: `{{ a.price_cup|money }}`, `{{ a.cups_year[0]|num }}`, `{{ a.cit_rate|pct }}`
- Kết quả: `{{ fin.base.last.revenue|ty }}` (tỷ đ), `{{ fin.base.metrics.breakeven_year }}`, `{{ fin.bear.metrics.funding_gap|money }}`
  - `fin.<kịch bản>.years[i]`: year, revenue, cogs, gross_profit, gross_margin, opex, ebitda, tax, net_income, capex, fcf, cash_end, cum_fcf, streams.<id>
  - `fin.<kịch bản>.metrics`: raise_amount, founder_capital, pre_money, post_money, investor_stake, breakeven_year, payback_year,
    min_cash, funding_gap, npv, exit_value, investor_exit, investor_moic
  - `fin.<kịch bản>.segments.<id>`: name, years[i].{revenue, gross_profit, direct_opex, contribution, margin}, last, total_revenue, total_contribution
- Bộ lọc: `money` (đơn vị meta, tự bỏ ,0), `ty` (triệu → tỷ), `num(d)`, `pct(d)`
- Nguồn: `{{ cite('ev-jll-q2') }}` → "(JLL, 2026)"; danh mục đầy đủ có URL nằm ở Excel và trình xem.
- Partials: `{% include "partials/pnl.md.j2" %}`, `segments.md.j2`, `draft.md.j2`
- `gen.py check` báo ERROR khi thấy số tiền/% gõ tay trong văn bản, nguồn không tồn tại, `verified` thiếu nguồn, kịch bản base âm tiền.

## Số trong story.yaml / datasets.yaml / products.yaml
- Dữ kiện có nguồn (giá đối thủ, quy mô thị trường…) ghi thẳng, kèm `src`/`sources`.
- Kết quả **model** (doanh thu, hoà vốn, biên…) viết bằng Jinja để tự cập nhật khi đổi giả định:
  `takeaway: "Doanh thu {{ fin.base.last.year }} đạt {{ fin.base.last.revenue|ty }}"`, `value: "{{ fin.base.metrics.breakeven_year }}"`.
  `tools/export.py` render các chuỗi này; `gen.py check` báo lỗi nếu biểu thức sai và nhắc những chỗ số tiền/% gõ tay.
- `gen.py check` còn có **cảnh báo độ hợp lý**: biên EBITDA > 45%, có lãi ngay năm đầu, doanh thu tăng > 4×/năm, MOIC > 20×,
  kịch bản xấu thiếu tiền. Không chặn build — nhưng nhà đầu tư sẽ hỏi đúng những chỗ đó.
- `verified` phải có ít nhất một nguồn **bên ngoài**: nguồn `type: founder | interview | internal | estimate` hay `ev-000` không đủ.
