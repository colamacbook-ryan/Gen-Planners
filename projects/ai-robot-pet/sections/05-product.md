# Sản phẩm: pet tháo rời não–thân

## Thiết kế lõi

```
 NÃO (module tháo rời: ESP32-S3, mic, loa, màn hình mắt, camera)
   │  gắn vào
   ├── Thân bánh xe / thân chó 4 chân / thân thú bông / đế để bàn  ← bán thêm, sưu tầm
   │
   │  WebSocket / MQTT (firmware mở xiaozhi, trỏ về server của ta)
   ▼
 SERVER TẠI VIỆT NAM
   ├─ Giọng nói tiếng Việt 3 miền + tiếng Anh
   ├─ Tính cách & trí nhớ riêng cho từng pet ("huấn luyện" được)
   ├─ Gói kỹ năng: bạn đồng hành · luyện tiếng Anh · chăm sóc ông bà · trò chơi · lập trình
   └─ Bộ lọc an toàn cho trẻ em, dữ liệu lưu trong nước
        │
        ▼
 App: huấn luyện pet, theo dõi, thi đấu, mua thân/skin/kỹ năng
```

Vì sao tháo rời não–thân là mại điểm thật:
- **Một não, nhiều thân** → người dùng mua thêm thân thay vì mua máy mới; ta bán thân với biên cao như hàng sưu tầm.
- **Nâng cấp não** không phải bỏ thân → dịch vụ nâng cấp ở CLB.
- **Dùng cho giáo dục**: học sinh lắp thân, lập trình hành vi — cùng sản phẩm, thêm thị trường.
- Tham chiếu: LOOI dùng điện thoại làm não, gọi vốn cộng đồng thành công trên Kickstarter; Hiwonder MechDog là kit não ESP32 + thân robot chó (research/02).

## Giá và giá vốn

| | Giá bán (giả định) | Giá vốn |
|---|---|---|
| Bộ pet (não + 1 thân) | {{ a.pet_price|money(2) }} | Về kho khoảng {{ a.fact_landed_pet }} USD {{ cite('ev-alibaba-aipets') }}; tổng giá vốn + kênh {{ a.pet_cogs|pct }} giá bán |
| Gói kỹ năng | {{ (a.brain_sub_price / 12 * 1000)|num }} nghìn đ/tháng | Chi phí AI mục tiêu dưới {{ a.gate_cloud_cost }} nghìn đ/pet/tháng khi tự vận hành {{ cite('ev-xiaozhi', 'ev-deepseek-pricing') }} |
| Thân, skin, phụ kiện | Chi tiêu TB {{ a.acc_spend|money(1) }}/pet/năm | Giá vốn {{ a.acc_cogs|pct }} nhờ thiết kế riêng |

Chi phí AI dùng API realtime cao cấp khoảng {{ a.fact_cloud_realtime }} USD/người/tháng {{ cite('ev-openai-pricing') }} — vượt giá gói kỹ năng. Vì vậy **phải tự vận hành phần giọng nói và dùng mô hình rẻ** (khoảng {{ a.fact_cloud_selfhost }} USD/tháng trở xuống).

## Nguồn hàng & lắp ráp

- Nhà máy Thâm Quyến có sẵn thiết bị AI companion, giá niêm yết từ vài chục USD; OEM thật (logo, firmware, server riêng) từ khoảng 1.000 bộ {{ cite('ev-alibaba-aipets') }}.
- **Lắp ráp tại VN**: nhập não và thân dạng linh kiện/bán thành phẩm, lắp, nạp firmware, kiểm tra, đóng gói tại VN — đủ để ghi "lắp ráp tại Việt Nam", kiểm soát chất lượng, và làm dịch vụ sửa chữa.
- Chuyến khảo sát Thâm Quyến khoảng {{ a.trip_budget|money(0) }}/người/5 ngày; đội nói tiếng Trung đàm phán trực tiếp.

## Việc cần người thật làm

- RFQ 3–5 nhà máy cho thiết kế não tháo rời + 2 loại thân; đặt mẫu.
- Nạp firmware trỏ về server riêng, thử giọng tiếng Việt với 30 người.
- Đo chi phí AI thật trên 20 pet trong 4 tuần.
