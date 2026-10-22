# Rủi ro, phản biện & khi nào KHÔNG nên đầu tư

| Rủi ro | Khả năng | Tác động | Giảm thiểu |
|---|---|---|---|
| Người dùng chán pet sau vài tuần (TQ: trả hàng khoảng {{ a.fact_return_rate|pct }}) {{ cite('ev-36kr-returns') }} | Cao | Rất cao | CLB, giải đấu, huấn luyện, thân mới — đo tỷ lệ quay lại ở giai đoạn 0 |
| CLB lỗ vì mặt bằng + nhân sự cố định | Trung bình | Cao | Bắt đầu bằng góc trải nghiệm chia doanh thu; CLB chỉ mở khi đã có khách |
| Nhượng quyền mở quá nhanh, chất lượng kém | Trung bình | Cao | Chỉ nhượng quyền khi CLB đầu có lãi ≥ 1 năm; sổ tay vận hành chuẩn |
| Sự cố nội dung với trẻ em {{ cite('ev-folotoy') }} | Trung bình | Rất cao | Bộ lọc an toàn, red-team, phụ huynh kiểm soát |
| Vi phạm luật dữ liệu / luật AI {{ cite('ev-pdp-law', 'ev-ai-law') }} | Trung bình | Cao | Server VN, luật sư từ đầu |
| Hàng giá rẻ trên sàn TMĐT cạnh tranh giá | Cao | Trung bình | Không đua giá máy; bán hệ sinh thái + IP riêng |
| Chi phí AI cao hơn giá gói kỹ năng | Trung bình | Trung bình | Tự host giọng nói, mô hình rẻ, giới hạn dùng |
| Đội nhỏ ôm nhiều mảng | Cao | Cao | Đi đúng thứ tự: pet + góc trải nghiệm → học viện → CLB → nhượng quyền |

## Câu hỏi khó và câu trả lời

1. **"Shopee bán robot rẻ hơn, sao khách mua của ta?"** — Vì họ mua bạn đồng hành nói tiếng Việt, có CLB để chơi, có giải để thi, có thân mới để sưu tầm. Hàng sàn không có những thứ đó.
2. **"CLB có lỗ không?"** — Mở góc trải nghiệm chia doanh thu trước, chi phí thấp; chỉ mở CLB khi góc chứng minh lượng khách. Kịch bản CLB chỉ đạt sáu phần mười kế hoạch vẫn hoà vốn năm {{ fin.club_weak.metrics.breakeven_year }}.
3. **"Mất bao lâu có lãi?"** — Cơ sở: hoà vốn EBITDA năm {{ fin.base.metrics.breakeven_year }}; kịch bản xấu năm {{ fin.bear.metrics.breakeven_year or "—" }} và cần thêm vốn.
4. **"Tiền của tôi rủi ro tối đa bao nhiêu?"** — Giai đoạn 0 là {{ a.phase0_budget|money(0) }}; giai đoạn sau chỉ mở khi có số liệu.

## Khi nào KHÔNG nên đầu tư

- Pop-up và workshop không kéo được khách quay lại.
- Không đủ đơn đặt cọc ở mức giá dự kiến.
- Bộ não tiếng Việt không đạt chất lượng hoặc chi phí AI vượt giá gói kỹ năng.
- Đội không làm toàn thời gian cho giai đoạn 0–1.
