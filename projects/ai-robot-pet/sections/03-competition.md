# Chuỗi giá trị & cạnh tranh: tiền và lợi thế nằm ở đâu

## Bản đồ chuỗi giá trị

| Tầng | Ai đang làm | Biên lãi / lợi thế | Đội của ta nên ở đây? |
|---|---|---|---|
| 1. Chip, linh kiện, OEM | Espressif, nhà máy Thâm Quyến | Biên mỏng, quy mô quyết định | Không — chỉ mua |
| 2. Firmware thiết bị | Mã nguồn mở (xiaozhi, MIT) {{ cite('ev-xiaozhi') }} | Gần như miễn phí | Dùng lại, không xây |
| 3. Giọng nói tiếng Việt (ASR/TTS) | Viettel × iFLYTEK (cho thiết bị edge) {{ cite('ev-viettel-iflytek') }}, FPT, Zalo | Đang thành hạ tầng | Mua/tích hợp — không cạnh tranh trực diện |
| 4. **Bộ não: tính cách, trí nhớ, an toàn, nội dung, lưu dữ liệu tại VN** | **Chưa ai ở cấp tiêu dùng tiếng Việt** (research/06, research/07) | Cao, có hiệu ứng dữ liệu | **CÓ — lõi** |
| 5. Sản phẩm & thương hiệu | Hãng TQ (Fuzozo, BubblePal, Loona, Ropet…), chưa bản địa hoá cho VN | Trung bình–cao nếu giữ được người dùng | Có — 2 sản phẩm tự làm để chứng minh bộ não |
| 6. Phân phối | Shopee/TikTok Shop, trung tâm tiếng Anh, trường, hội người cao tuổi | Kênh B2B2C rẻ hơn quảng cáo | Đối tác |
| 7. Dịch vụ & cộng đồng | Sửa chữa, CLB, sự kiện | Doanh thu nhỏ, củng cố thương hiệu | Giai đoạn sau |

**Kết luận:** lợi nhuận bền nằm ở tầng 4 (bộ não) + tầng 5 khi có thuê bao. Tầng 1–3 đang thành hàng hoá — đó là tin tốt, vì ta mua được rẻ.

## Đối thủ và người có thể trở thành đối thủ

| Đối thủ | Thế mạnh | Điểm yếu với thị trường VN | Cách ta đối phó |
|---|---|---|---|
| Hãng AI toy Trung Quốc | Sản phẩm, giá, kinh nghiệm | Không có tiếng Việt tự nhiên, không lưu dữ liệu tại VN, rủi ro pháp lý dữ liệu trẻ em | **Biến họ thành khách hàng** của nền tảng (đội nói tiếng Trung) |
| Nền tảng TQ (Volcano/Doubao, JoyInside) | Quy mô, chi phí | Dữ liệu ra nước ngoài → vướng luật BVDLCN {{ cite('ev-pdp-law') }} | Định vị "tuân thủ VN, an toàn trẻ em có chứng minh" |
| Viettel × iFLYTEK | Giọng nói tiếng Việt, kênh viễn thông | Làm hạ tầng/loa chung, không làm tính cách + nội dung cho người già/trẻ em | Dùng như nhà cung cấp ASR/TTS; hợp tác kênh |
| App học tiếng Anh (ELSA, Duolingo) | Nội dung, người dùng | Cần màn hình; phụ huynh ngại màn hình | Thiết bị không màn hình bổ trợ, có thể hợp tác nội dung |
| Trung tâm STEM (Teky, MindX) | Kênh học viên | Không làm phần cứng AI riêng | Bán gói kit + giáo án cho họ |
| Robot người già nội địa (Naiscorp) | Đi trước về giải thưởng | Chưa có quy mô | Theo dõi; khác biệt bằng kênh "con cháu" và thuê bao |

## Hào bảo vệ (moat) có thể xây

1. **Dữ liệu giọng nói tiếng Việt của người già và trẻ em theo vùng miền** — hiện rất khan hiếm (bộ dữ liệu hội thoại mở lớn nhất chỉ vài trăm giờ) {{ cite('ev-vn-speech-data') }}.
2. **Bộ lọc an toàn có thể chứng minh** cho trẻ em/người già — sau các sự cố như FoloToy {{ cite('ev-folotoy') }}, đây là thứ phụ huynh và đối tác sẽ trả tiền.
3. **Tuân thủ pháp lý Việt Nam** (dữ liệu tại VN, đồng ý của phụ huynh, nhãn AI) {{ cite('ev-pdp-law', 'ev-ai-law') }} — hãng nước ngoài khó làm nhanh.
4. **Quan hệ nhà máy Thâm Quyến bằng tiếng Trung** — rút ngắn vòng lặp sản phẩm, đàm phán OEM ở MOQ thấp.
5. **Hiệu ứng nền tảng**: mỗi thương hiệu tích hợp thêm → thêm dữ liệu → bộ não tốt hơn → thu hút thêm thương hiệu.

Trung thực: hào 1–3 mất 2–3 năm để thành hình và không bất khả xâm phạm — Viettel, FPT hoặc nền tảng TQ có thể làm tương tự. Lợi thế thật của đội nhỏ là **tốc độ và sự tập trung vào 2 nhóm người dùng cụ thể** mà người lớn không ưu tiên.
