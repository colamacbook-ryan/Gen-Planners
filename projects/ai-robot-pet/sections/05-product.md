# Sản phẩm, công nghệ & nguồn hàng

## Kiến trúc: một bộ não, nhiều thân

```
 Thiết bị (mua OEM Thâm Quyến, ESP32-S3: mic, loa, có/không màn hình, camera)
        │  WebSocket / MQTT (firmware mở xiaozhi, trỏ về server của ta)
        ▼
 BỘ NÃO (server đặt tại Việt Nam)
   ├─ Nhận dạng giọng tiếng Việt (ASR) — mua/tích hợp, tinh chỉnh cho giọng người già, trẻ em, 3 miền
   ├─ Tính cách & trí nhớ dài hạn — mỗi người dùng một "người bạn" nhớ chuyện cũ
   ├─ Bộ lọc an toàn 2 lớp — trẻ em / người già (lừa đảo, y tế, nội dung nhạy cảm)
   ├─ Mô hình ngôn ngữ — lớp chuyển đổi nhiều nhà cung cấp, ẩn danh trước khi gọi API nước ngoài
   ├─ Nội dung — giáo án tiếng Anh theo cấp độ, chuyện kể, nhắc thuốc, trò chơi trí nhớ
   └─ Tổng hợp giọng (TTS)
        │
        ▼
 App gia đình (con cái / phụ huynh): tóm tắt hằng ngày, cảnh báo, cài đặt
```

Firmware mở cho phép tự host server — chỉ cần đổi địa chỉ và nạp lại {{ cite('ev-xiaozhi') }}. Đây là lý do một đội nhỏ có thể có sản phẩm chạy thật trong vài tuần.

## Hai sản phẩm đầu tiên

| | "Con cháu" (người già) | Bạn luyện nói tiếng Anh |
|---|---|---|
| Hình dạng | Loa/thú bông để bàn, nút bấm to, không màn hình | Thú bông hoặc robot để bàn, không màn hình |
| Giá máy (giả định) | {{ a.elder_price|money(2) }} | {{ a.eng_price|money(2) }} |
| Thuê bao (giả định) | {{ (a.elder_sub_price / 12 * 1000)|num }} nghìn đ/tháng | {{ (a.eng_sub_price / 12 * 1000)|num }} nghìn đ/tháng |
| Tính năng lõi | Trò chuyện hằng ngày theo giọng địa phương, nhắc thuốc, kể chuyện, phát hiện cuộc gọi lừa đảo, tóm tắt cho con | 15 phút luyện nói mỗi ngày theo trình độ sách giáo khoa, sửa phát âm, báo cáo tiến bộ cho phụ huynh |
| Người mua | Con cái | Phụ huynh / trung tâm tiếng Anh |

## Nguồn hàng & giá vốn (chi tiết research/02)

- **Thị trường nguồn:** nhiều nhà cung cấp Thâm Quyến/Đông Quản, giá niêm yết từ vài chục USD; OEM thật (logo, firmware, server riêng) bắt đầu khoảng 1.000 máy {{ cite('ev-alibaba-aipets') }}.
- **Giá về kho ước tính:** khoảng {{ a.fact_landed_low }} USD/máy (loại giọng nói cơ bản), {{ a.fact_landed_mid }} USD/máy (để bàn có màn hình + camera), đã gồm vận chuyển, VAT, hợp quy, bao bì {{ cite('ev-alibaba-aipets', 'ev-freight', 'ev-hs-9503') }}.
- **Chi phí AI mỗi người dùng/tháng:** khoảng {{ a.fact_cloud_realtime }} USD nếu dùng API realtime cao cấp; mục tiêu dưới {{ a.fact_cloud_selfhost }} USD khi tự host ASR/TTS + mô hình rẻ {{ cite('ev-openai-pricing', 'ev-deepseek-pricing') }}. **Đây là ràng buộc thiết kế số 1**: chi phí AI là giá vốn lặp lại hằng tháng nên phải có thuê bao và giới hạn sử dụng hợp lý.
- **Chuyến khảo sát Thâm Quyến:** khoảng {{ a.trip_budget|money(0) }}/người/5 ngày.

## Việc cần người thật làm

- Gửi yêu cầu báo giá (RFQ) cho 3–5 nhà máy OEM Thâm Quyến ở mức 1.000 máy; đặt mẫu, nạp firmware trỏ về server riêng để thử.
- Đo chất lượng nhận dạng giọng tiếng Việt với 30+ người già và 30+ trẻ em ở 3 miền.
- Đo chi phí AI thật trên 20 người dùng thử trong 4 tuần.
