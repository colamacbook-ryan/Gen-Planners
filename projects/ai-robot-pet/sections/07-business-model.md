{% set b = fin.base %}
{% set s = b.segments %}
# Mô hình kinh doanh: vòng quay hệ sinh thái

## Vòng quay

```
   Góc trải nghiệm / CLB  ──►  khách chơi thử, mua pet
          ▲                          │
          │                          ▼
   thi đấu, workshop,          pet về nhà: dùng gói kỹ năng,
   khoe pet, F&B               mua thân/skin, học huấn luyện
          ▲                          │
          └──────── quay lại CLB ◄───┘
                     │
                     ▼
        CLB có lãi → nhượng quyền → thêm điểm bán pet
```

Mỗi pet bán ra không phải là kết thúc giao dịch mà là **mở đầu một dòng chi tiêu**: thân mới, skin, gói kỹ năng, khoá học, sửa chữa, vé CLB.

## Bảy dòng tiền

| Dòng tiền | Cách thu | Giả định chính |
|---|---|---|
| Bán pet | Một lần | {{ a.pet_price|money(2) }}/bộ, giá vốn + kênh {{ a.pet_cogs|pct }} |
| Thân, skin, phụ kiện | Lặp lại theo pet đang dùng | {{ a.acc_spend|money(1) }}/pet/năm; {{ a.pet_active|pct }} pet đã bán còn hoạt động |
| Gói kỹ năng não | Thuê bao | {{ a.brain_sub_price|money(2) }}/năm; {{ a.brain_sub_rate|pct }} pet có gói |
| CLB & góc trải nghiệm | Vé, hội viên, F&B, sự kiện | Góc {{ a.corner_rev|ty }}/năm; CLB {{ a.club_rev|ty }}/năm, chi phí {{ a.club_opex|ty }}/năm |
| Học viện & giáo dục | Khoá 4 tuần; gói cho trường | {{ a.academy_fee|money(1) }}/khoá; {{ a.edu_package|money(0) }}/trường/năm |
| Sửa chữa, nâng cấp | Theo pet đang dùng | {{ a.service_spend|money(1) }}/pet/năm |
| Nhượng quyền | Phí ban đầu + phí theo doanh thu | {{ a.fr_fee|money(0) }}/CLB; {{ a.fr_royalty|pct }} doanh thu |

## Lợi nhuận đóng góp theo mảng (kịch bản cơ sở)

{% with scenario = "base" %}{% include "partials/segments.md.j2" %}{% endwith %}


## Đọc bảng

- **Bán pet** là mảng đóng góp lớn nhất ({{ s.pet.last.contribution|ty }} năm {{ b.last.year }}) — nhập rẻ, bán theo thương hiệu riêng có lãi tốt, đúng như ý tưởng gốc.
- **Học viện** ({{ s.academy.last.contribution|ty }}) và **gói kỹ năng** ({{ s.brain.last.contribution|ty }}) là hai mảng tăng nhanh, biên cao, ít vốn.
- **Phụ kiện + dịch vụ** ({{ (s.acc.last.contribution + s.service.last.contribution)|ty }}) đến từ thiết kế tháo rời và số pet tích luỹ.
- **CLB** đóng góp {{ s.club.last.contribution|ty }} — biên mỏng hơn vì mặt bằng và nhân sự, nhưng là **cỗ máy bán hàng và giữ chân** cho mọi mảng khác.
- **Nhượng quyền** ({{ s.franchise.last.revenue|ty }} doanh thu năm cuối) gần như không tốn vốn của ta và nhân rộng điểm bán pet.

## Đơn vị kinh tế cần chứng minh

- Khách quay lại CLB/workshop lần 2 ≥ {{ a.gate_return|pct }}.
- Người mua còn dùng pet ở tuần 6 ≥ {{ a.gate_pet_use|pct }}.
- Chi phí AI ≤ {{ a.gate_cloud_cost }} nghìn đ/pet/tháng.
