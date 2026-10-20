# Toàn cảnh lĩnh vực: Embodied AI tiêu dùng

## Lĩnh vực này thực chất là gì

"Robot pet AI" chỉ là một hình dạng. Lĩnh vực thật là **embodied AI tiêu dùng**: đồ vật rẻ có tai, miệng, đôi khi có mắt và bánh xe, còn **bộ não là mô hình ngôn ngữ lớn (LLM) trên cloud**. Hai đường cong vừa cắt nhau:

- **Phần cứng sụp giá.** Linh kiện cho một trợ lý giọng nói ESP32 dưới khoảng 60 NDT (research/06); giá FOB các thiết bị AI companion từ vài chục USD {{ cite('ev-alibaba-aipets') }}.
- **AI biết nghe-nói sụp giá.** Một người dùng trò chuyện 20 phút mỗi ngày tốn khoảng {{ a.fact_cloud_realtime }} USD/tháng nếu dùng API realtime cao cấp {{ cite('ev-openai-pricing') }}, nhưng chỉ khoảng {{ a.fact_cloud_selfhost }} USD/tháng nếu tự vận hành pipeline giọng nói + mô hình rẻ {{ cite('ev-xiaozhi', 'ev-deepseek-pricing') }}.

Hệ quả: **bất kỳ đồ vật nào cũng có thể biết nói chuyện, ghi nhớ và dạy**. Câu hỏi khai phá: ở Việt Nam, điều đó giải quyết nỗi đau nào mà ai đó sẵn sàng trả tiền đều đặn?

## Bằng chứng từ thị trường đi trước (Trung Quốc)

| Tín hiệu | Dữ liệu |
|---|---|
| Quy mô | Khoảng {{ a.fact_cn_aitoy_2025 }} tỷ NDT (2025) → tới {{ a.fact_cn_aitoy_2030 }} tỷ NDT (2030) {{ cite('ev-caixin-aitoy', 'ev-mittr-aitoy') }} |
| Sản phẩm đại chúng thành công | Fuzozo bán khoảng {{ a.fact_fuzozo_units|num }} máy, người dùng trò chuyện TB {{ a.fact_fuzozo_minutes }} phút/ngày {{ cite('ev-pedaily-fuzozo') }} |
| Ai mua | Khoảng {{ a.fact_fuzozo_female|pct }} người dùng cốt lõi của Fuzozo là **nữ trưởng thành** — nhu cầu thật là *bạn đồng hành*, không chỉ đồ chơi trẻ em {{ cite('ev-pedaily-fuzozo') }} |
| Biên lãi phần cứng | Từ {{ a.fact_cn_margin_lo|pct }} (phân khúc thấp) tới {{ a.fact_cn_margin_hi|pct }} (phân khúc cao) {{ cite('ev-36kr-margin') }} |
| Nền tảng bộ não | Doubao (ByteDance) chạy trên hơn {{ a.fact_doubao_devices|num }} thiết bị; JD có nền tảng JoyInside cho hàng chục thương hiệu {{ cite('ev-36kr-ropet') }} |
| Mặt tối | Trả hàng do hết hứng thú khoảng {{ a.fact_return_rate|pct }} {{ cite('ev-36kr-returns') }}; chiến tranh giá; sự cố an toàn nội dung trẻ em (FoloToy) {{ cite('ev-folotoy') }}; công ty chết làm thiết bị "chết theo" (Moxie) {{ cite('ev-moxie') }} |
| Người thắng | Ai giữ được người dùng: Ropet tự công bố giữ {{ a.fact_ropet_retention|pct }} người dùng sau 90 ngày {{ cite('ev-36kr-ropet') }} |

**Bài học:** tiền không nằm ở cái vỏ. Tiền nằm ở (1) giữ chân người dùng bằng tính cách, trí nhớ, nội dung; (2) thuê bao; (3) nền tảng bộ não dùng chung cho nhiều thương hiệu.

## Việt Nam: những lực đẩy cấu trúc

| Lực | Dữ liệu | Ý nghĩa |
|---|---|---|
| Già hoá nhanh nhất khu vực | {{ a.fact_vn_60plus }} triệu người 60+ → {{ a.fact_vn_60plus_2050 }} triệu năm 2050; xã hội già quanh {{ a.fact_vn_aged_year }} {{ cite('ev-unfpa-ageing', 'ev-nso-census') }} | Con cái đi làm xa, người già thiếu người trò chuyện — nhu cầu tăng chắc chắn mỗi năm |
| Tầng lớp có tiền | {{ a.fact_vn_abcd_hh }} triệu hộ thu nhập trung bình trở lên {{ cite('ev-cimigo-abcd') }} | Đủ lớn cho sản phẩm vài triệu đồng + thuê bao |
| Quen với AI và trả tiền | {{ a.fact_vn_ai_users|pct }} người dùng online đã dùng AI; {{ a.fact_vn_ai_paying|pct }} người dùng AI trả phí {{ cite('ev-decisionlab-ai') }} | Thói quen trả tiền cho AI đã hình thành |
| Chi cho "bạn đồng hành" | {{ a.fact_vn_pet_owners|pct }} người trưởng thành đô thị nuôi thú cưng {{ cite('ev-pet-vn') }} | Túi tiền cảm xúc lớn hơn túi tiền đồ chơi |
| Chi cho tiếng Anh | Phụ huynh đã chi {{ a.fact_vn_english_spend_lo }}–{{ a.fact_vn_english_spend_hi }} triệu/tháng; {{ a.fact_vn_no_online|pct }} không chấp nhận học hoàn toàn online {{ cite('ev-english-parents') }} | Muốn luyện nói hằng ngày nhưng không muốn thêm màn hình |
| Chính sách giáo dục | AI vào toàn bộ khoảng {{ a.fact_vn_schools|num }} trường từ 2026-27 {{ cite('ev-qd2422') }}; tiếng Anh là ngôn ngữ thứ hai tới 2035 {{ cite('ev-qd2371') }} | Nhu cầu 10–15 năm do nhà nước tạo ra |
| Độ trễ thị trường | Robot hút bụi VN +{{ a.fact_vn_vacuum_growth|pct }}/năm, hãng TQ áp đảo {{ cite('ev-vacuum-vn') }} | Thiết bị AI TQ sẽ tràn vào — chúng cần bộ não tiếng Việt |

So sánh: toàn bộ thị trường đồ chơi Việt Nam chỉ khoảng {{ a.fact_vn_toys }} triệu USD {{ cite('ev-imarc-toys') }}. Nếu chỉ nhìn như "đồ chơi", lĩnh vực này nhỏ. Nhìn như **lớp trí tuệ cho thiết bị phục vụ người già, giáo dục và bạn đồng hành**, nó chạm vào những túi chi tiêu lớn hơn nhiều và tăng trưởng theo cấu trúc dân số.
