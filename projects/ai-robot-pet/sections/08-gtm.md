# Lộ trình & các cửa ải

Nguyên tắc: **mỗi giai đoạn chỉ mở khi cửa ải trước đã qua bằng số liệu thật.** Không qua thì dừng hoặc đổi hướng — thiệt hại giới hạn trong ngân sách giai đoạn đó.

## Giai đoạn 0 — Kiểm chứng (8–12 tuần, {{ a.phase0_budget|money(0) }})

| Thí nghiệm | Làm gì | Ngân sách | Qua khi |
|---|---|---|---|
| A. Sản phẩm | Chuyến Thâm Quyến, mẫu OEM não tháo rời + 2 thân, nạp firmware trỏ server VN, giọng tiếng Việt | {{ a.exp_a_budget|money(0) }} | Pet nói tiếng Việt tự nhiên; chi phí AI ≤ {{ a.gate_cloud_cost }} nghìn đ/pet/tháng |
| B. Góc pop-up | 4 cuối tuần trong một quán cà phê/TTTM: chơi thử, đặt cọc | {{ a.exp_b_budget|money(0) }} | ≥ {{ a.gate_popup_visits }} lượt khách/cuối tuần |
| C. Workshop & giải đấu | Workshop huấn luyện pet có thu phí + một giải đấu nhỏ | {{ a.exp_c_budget|money(0) }} | ≥ {{ a.gate_return|pct }} người quay lại lần 2 |
| D. Đặt cọc online | TikTok/Facebook + landing page | {{ a.exp_d_budget|money(0) }} | Tổng ≥ {{ a.gate_preorders }} đơn đặt cọc (cả B và D) |

**Cửa ải 1:** A qua + có đủ đơn đặt cọc + B hoặc C cho thấy khách quay lại.

## Giai đoạn 1 — Ra mắt (12 tháng, {{ a.phase1_budget|ty }})

- Lô OEM đầu, hợp quy QCVN, lắp ráp và kiểm tra tại VN.
- 3 góc trải nghiệm (HN, TP.HCM), học viện khoá đầu, cộng đồng online.
- Gói kỹ năng: bạn đồng hành, luyện tiếng Anh, chăm sóc ông bà.

**Cửa ải 2:** ≥ {{ a.gate_pet_use|pct }} người mua còn dùng ở tuần 6; góc trải nghiệm có lãi vận hành; doanh thu ngoài bán pet tăng đều.

## Giai đoạn 2 — Mở rộng (năm 2–5, {{ a.phase2_budget|ty }})

- Mỗi năm một CLB flagship (từ năm {{ fin.base.years[1].year }}).
- Nhượng quyền khi CLB đầu có lãi ≥ 1 năm (từ năm {{ fin.base.years[2].year }}).
- Gói giáo án cho trường tư, trung tâm STEM.
