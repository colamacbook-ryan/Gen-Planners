# R2 — Nguồn hàng Trung Quốc, BOM, chi phí cloud, logistics

Thu thập 2026-10-20. Giá Alibaba là giá niêm yết (thường là trader), cần RFQ ở 1.000 pcs. EST = ước tính.

## Sản phẩm & giá FOB niêm yết
| Loại | Ví dụ | Giá | MOQ | Nguồn |
|---|---|---|---|---|
| AI plush/toy | Shenzhen ESYS (OEM) | $15–22 | 1.000 | electronics.alibaba.com/product/ai-companions |
| AI plush | Suzhou Ruiguan (OEM/ODM) | $26,7–28,9 | 50 | m.made-in-china.com/company-ruiguandz/ |
| Desktop pet màn hình | Shenzhen Honest-Great; Beijing Qingyang (3,6", cam 1080p) | $35,7; $44–49 | 5–10 | electronics.alibaba.com/product/ai-robotic-pets |
| Desktop robot | Shenzhen Maodelin | $49–99, lead 30–45 ngày | – | sourcing.hktdc.com |
| Robot bánh xe/chó | Shenzhen Yoosure; Qianzhi Xiaoyin (multimodal) | $34–42; $158–168 | 1 | ai-robotic-pets |
| Kit giáo dục mô-đun | Hiwonder MechDog (ESP32, 8DOF, open source) | $299,9–569,9 | 1 | ai-robotic-pets |

Nhận xét: OEM thật (firmware + server riêng) xuất hiện ở ~1.000 pcs. Kit "não tháo rời" giá sỉ không tìm thấy → là dự án ODM tuỳ biến.

## Nền tảng mở cho backend riêng
- **xiaozhi-esp32** (MIT, 31,6k sao, 138 cấu hình board) — tự host server (Python/Java/Go), đổi URL + flash lại. https://github.com/78/xiaozhi-esp32
- Kit ESP32-S3 xiaozhi ~US$25; Espressif EchoEar €36,78 (hỗ trợ OpenAI/Gemini/Xiaozhi); Yahboom Raspbot V2 từ $134,99; Petoi Bittle X $237–279.

## BOM ước tính (desktop pet giọng nói + camera)
ESP32-S3 N16R8 $4,3–4,5 (DigiKey); camera OV2640 ~£2,45; khối lõi (机芯) < ¥50, có màn hình ≈ ¥80 (huxiu 2026-01-05 https://www.huxiu.com/article/4823539.html); motor, màn hình, vỏ, lắp ráp EST → **BOM xuất xưởng EST $20–28**. Biên gộp báo cáo: 50–65% (cơ bản), 70–85% (¥1.500–3.000).

## Chi phí cloud mỗi user hoạt động/tháng (20 phút/ngày, EST)
| Stack | $/user/tháng |
|---|---|
| gpt-realtime-mini speech-to-speech | ≈ 8,1 |
| Gemini Flash Live | ≈ 7,3 (giá Gemini Flash/TTS tăng gấp đôi từ 01/01/2027) |
| Cascade ASR + DeepSeek + TTS | ≈ 4,8 |
| Tự host ASR/TTS (FunASR/Edge TTS qua xiaozhi-server) + DeepSeek | EST 0,5–1,5 |
| Tham chiếu TQ: đồ chơi dùng Doubao | ¥6–10/thiết bị/**năm** (dùng ít) — finance.sina.cn 2026-06-25 |

→ Cloud là giá vốn lặp lại hằng tháng: phải có thuê bao hoặc giới hạn mức dùng; xây lớp chuyển đổi nhà cung cấp.

## Logistics & thủ tục
- LCL ~$18–50/cbm, 9–17 ngày; FCL 20' $360–440, 40' $675–825; đường bộ $1,5–3/kg, 2–7 ngày (sino-shipping, freightamigo).
- HS 9503.00.99: MFN 20%, **ACFTA 0% với C/O form E**, VAT 5%; QCVN 3:2019/BKHCN (caselaw.vn/chi-tiet-ma-hs/95030099).
- Wi-Fi: thử nghiệm QCVN 54:2020, dấu CR; cơ quan quản lý nay là Bộ KH&CN (TT 29/2025, 36/2026).
- Tiểu ngạch: không khấu trừ VAT, rủi ro truy thu, không có hợp quy → **không khả thi cho sản phẩm thương hiệu**.
- Chuyến khảo sát Thâm Quyến/Quảng Châu 5 ngày/người EST 15–22 tr.

## Landed cost/đơn vị (lô OEM ~1.000, USD, EST)
| | Plush giọng nói | Desktop AI pet | Robot di động |
|---|---|---|---|
| FOB | 15 | 40 | 90 |
| NRE firmware/thương hiệu phân bổ | 5 | 8 | 15 |
| Vận chuyển | 0,5 | 1 | 2 |
| Thuế NK (form E) | 0 | 0 | 0 |
| VAT NK | 0,8 | 4,1 | 9,2 |
| Hợp quy phân bổ | 5 | 5 | 8 |
| Bao bì VN + dự phòng lỗi | 1,5 | 2,5 | 4,5 |
| **Landed** | **≈ 28** | **≈ 61** | **≈ 129** |
| Cloud/user/tháng | 1–5 | 5–8 | 5–8 + vision |

## Việc cần người thật làm
RFQ 3–5 OEM Thâm Quyến @1.000 pcs; đặt mẫu, test với server riêng; broker xác nhận HS + form E; báo giá lab QCVN 3 + CR; báo giá vận chuyển Hải Phòng/Cát Lái.
