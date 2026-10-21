# Gen Planner SaaS

Lớp SaaS bọc quanh chuẩn plan-as-code của repo: người dùng tạo dự án → **phỏng vấn founder** → **brainstorm & chốt điểm**
→ **brief** → **Chạy Plan** (core agent nghiên cứu + dựng SSOT) → **Hồ sơ** (console, dashboard, Word/PowerPoint/Excel).
Owner quản trị mọi thứ ở `/admin`.

```
Người dùng (/app)                           Owner / admin (/admin)
  ├─ Dự án mới (tên + ý tưởng)                ├─ Tổng quan: người dùng, dự án, job, token 30 ngày
  ├─ 1 Phỏng vấn  ← pipeline/interview.yaml   ├─ Người dùng: vai trò, khoá/mở, hạn mức dự án & lần chạy
  ├─ 2 Brainstorm → bảng chốt điểm            ├─ Dự án, Jobs (log trực tiếp, huỷ, chạy lại)
  ├─ 3 Brief (tự biên dịch, neo founder-first)├─ Core agent: cài CLI, nhiều tài khoản, đăng nhập qua terminal web,
  ├─ 4 Chạy Plan → hàng đợi job               │   chọn model, xem quota (/usage), ngân sách token, tự chuyển tài khoản
  └─ 5 Hồ sơ  ← studio/index.html (REST)      ├─ Quota & usage, Cài đặt (đăng ký, Google OAuth, ai trả phí), Nhật ký
```

## Hai nguồn AI, tách bạch

| | Dùng cho | Ai trả tiền | Cấu hình |
|---|---|---|---|
| **API key của user** (BYOK) | Trợ lý phỏng vấn, brainstorm; và Chạy Plan nếu là key Anthropic/Gemini | User | `/app#settings` — Anthropic, OpenAI, Gemini, OpenRouter. Key mã hoá Fernet, không bao giờ trả về trình duyệt |
| **Core agent của owner** | Chạy Plan | Owner (giới hạn bằng hạn mức lần chạy/tháng của từng user) | `/admin#agents` — Antigravity CLI (`agy`) mặc định, Claude Code CLI dự phòng |

Owner chọn ở Cài đặt: chạy Plan bằng tài khoản hệ thống, bằng key của user, hoặc để user chọn.
Không có key nào → chế độ **demo** (câu hỏi theo kịch bản, build từ template) nếu owner bật.

## Core agent: tài khoản, đăng nhập, quota

- Mỗi **agent profile** = một HOME riêng trong `GP_DATA/agents/<id>` → một tài khoản đăng nhập riêng. Đổi tài khoản = bấm
  *Dùng tài khoản này* trên profile khác; hoặc *Đăng xuất* rồi *Đăng nhập* lại trong profile đó.
- **Đăng nhập agy:** *Đăng nhập* mở terminal PTY ngay trên trang admin → chọn *Google OAuth* (Enter) → mở link hiện ra,
  đăng nhập Google, trang `antigravity.google/oauth-callback` cho mã → dán mã vào ô nhập của terminal.
- **Chế độ API key:** profile agy với Gemini API key (`modelProvider: gemini` + `GEMINI_API_KEY`), profile claude với Anthropic API key.
- **Claude Code (tài khoản):** *Đăng nhập* chạy `claude setup-token` → đăng nhập → CLI in token dài hạn → *Lưu token*.
- **Model:** *Lấy model* chạy `agy models` (cần đã đăng nhập) → chọn trong danh sách trên thẻ profile.
- **Quota:** token mỗi lần chạy đọc từ `usage` trong stream-json của CLI và cộng theo profile/tháng; đặt *ngân sách token* để
  thấy thanh tiến độ. Quota thật của gói (tín dụng còn lại) chỉ có trong TUI → *Xem quota* mở terminal gõ `/usage` và lưu
  văn bản đọc được.
- **Tự chuyển tài khoản:** job thất bại vì chưa đăng nhập / key sai / hết quota → profile bị đánh dấu, job chạy lại trên profile
  bật kế tiếp (theo *ưu tiên*), tối đa 3 lần.

## Chạy

```bash
pip install -r requirements.txt -r saas/requirements.txt      # + pandoc để xuất .docx/.pptx
curl -fsSL https://antigravity.google/cli/install.sh | bash   # core agent (hoặc bấm "Cài đặt CLI" trong admin)
uvicorn saas.server.main:app --port 8080                      # từ thư mục gốc repo
```

Mở `http://localhost:8080` → tài khoản đầu tiên đăng ký là **owner**. Docker: `docker compose -f saas/docker-compose.yml up -d`.

Khi chạy bằng root để cô lập agent (khuyến nghị — Dockerfile làm sẵn): `GP_DATA` phải nằm ở chỗ user `gpagent` đi qua được
(vd `/data`, `/var/lib/genplanner`; **không** đặt dưới `/root` hay thư mục 700), và CLI agent phải cài ngoài `/root`
(`/usr/local/bin` — nút *Cài đặt CLI* làm đúng như vậy). Trang Core agent báo ngay nếu một trong hai sai.

Biến môi trường: `GP_DATA` (mặc định `saas/data/`, đã gitignore), `GP_COOKIE_SECURE=1` khi chạy sau HTTPS,
`GP_SESSION_SECRET` / `GP_FERNET_KEY` nếu muốn quản lý khoá ngoài file. **Sao lưu `GP_DATA/fernet.key`** — mất file này là
mất mọi API key đã lưu.

Kiểm thử: `GP_DATA=$(mktemp -d) python -m pytest saas/tests -q` — 369 test (gồm 300 model ngẫu nhiên): luồng đầy đủ (kèm lịch sử phiên bản, lint, khôi phục); quét quyền mọi route (người lạ,
người dùng khác, user→admin, admin→owner); sửa số liệu trên mọi giả định thật; tách doanh thu định kỳ/một lần; đường ống agent với CLI giả lập (stream-json,
token, tiến độ, huỷ, hết quota → chuyển tài khoản, khởi động lại, job chỉ được nhận một lần); cô lập agent; agent ngoài qua API token; dữ liệu đầu vào lạ.

## Agent ngoài (Claude Code, Antigravity… của người dùng)

Người dùng chọn **Chạy Plan → Agent ngoài của tôi**: job chuyển sang trạng thái *chờ agent* và hiện một bản giao việc
(`pipeline/external-agent-prompt.md`). Người dùng tạo **API token** ở Cài đặt, đưa token + bản giao việc cho agent của mình.
Agent làm việc qua HTTP:

| Lệnh | Việc |
|---|---|
| `GET /api/jobs/{id}/handoff` | bản giao việc + danh sách file chuẩn |
| `GET /api/standard/<file>` | AGENTS.md, playbook, stages, template story/datasets… |
| `GET/PUT /api/projects/{slug}/ssot/<path>` | đọc/ghi SSOT (chỉ các đường dẫn cho phép, YAML được kiểm cú pháp, ≤ 2 MB) |
| `POST /api/projects/{slug}/check` | build + check, trả lỗi để sửa tới 0 ERROR |
| `POST /api/jobs/{id}/progress` · `/complete` | báo tiến độ · nộp bài → máy chủ build, kiểm link, xuất hồ sơ |

Header: `Authorization: Bearer gp_…`. Token không tạo được token khác, thu hồi là mất quyền ngay; chi phí AI do người dùng tự trả.

## Người dùng & owner

| | Có gì |
|---|---|
| **Cài đặt người dùng** | Hồ sơ & bảo mật (tên, mật khẩu, đăng xuất thiết bị khác) · Giao diện sáng/tối/hệ thống, thị trường mặc định · AI & API key · API token · Mức dùng theo tháng · Dữ liệu của tôi (tải .zip, xoá tài khoản) |
| **Dự án** | Đổi tên, sửa ý tưởng & thị trường, nhân bản (kèm bộ số liệu + lịch sử), lưu trữ, xoá; tìm dự án ở thanh bên |
| **Tổng quan owner** | Khoảng 7/30/90 ngày: người dùng mới, hoạt động tuần/tháng, tỉ lệ job thành công (tách lỗi hệ thống), thời gian chạy p50/p90, chờ hàng đợi, lý do lỗi hay gặp, token & chi phí, dung lượng từng phần + ổ đĩa, sức khoẻ hệ thống, cảnh báo cần xử lý; xuất CSV |
| **Cài đặt hệ thống** | Chung (tên, email hỗ trợ, URL công khai, thị trường mặc định) · Đăng ký & truy cập (mở/chỉ mời, giới hạn tên miền email, Google) · Chạy Plan & hạn mức · Vận hành (bảo trì chỉ-xem, thông báo toàn hệ thống, giữ log N ngày) · Sao lưu (.zip nhất quán) |

Quy tắc giao diện (token màu, khung trang, trạng thái, thuật ngữ): `saas/static/DESIGN.md`.

## Lịch sử phiên bản & kiểm tra số liệu

- Mỗi dự án là một repo git riêng trong workspace (`saas/server/history.py`). Mỗi mốc — chạy Plan, build lại, sửa số liệu,
  agent ngoài nộp bài, khôi phục — là một phiên bản; `build/` không vào git. Tab **Số liệu** → *Phiên bản*: xem diff,
  khôi phục (tạo phiên bản mới, không xoá lịch sử, rồi tự build lại).
- *Kiểm tra* chạy `gen.py check --json`: lỗi SSOT, schema `datasets.yaml`, `verified` phải có nguồn ngoài, cảnh báo
  hợp lý (biên EBITDA > 45%, lãi ngay năm 1, tăng trưởng > 4×/năm, MOIC > 20…). Tham chiếu DSL: `pipeline/model-reference.md`.

## Bảo mật

- Mật khẩu scrypt; phiên là cookie ký (HttpOnly, SameSite=Lax), khoá tài khoản hay đổi mật khẩu làm phiên cũ mất hiệu lực.
- Mọi lệnh ghi cần header `X-GP` (chặn CSRF từ form chéo site). Đăng nhập giới hạn 10 lần thất bại / 5 phút / IP và
  30 / 15 phút / tài khoản (xoay IP giả cũng bị chặn). Sau reverse proxy: đặt `FORWARDED_ALLOW_IPS` = IP proxy, không dùng `*`.
- Render hồ sơ: phép tính khổng lồ trong template bị chặn, tiến trình render có trần bộ nhớ (`GP_RENDER_MEM_MB`, mặc định 2048).
- Chỉ owner đặt lại mật khẩu cho admin.
- Dữ liệu dự án cô lập theo user; admin chỉ đọc. Trang Core agent và Cài đặt chỉ owner.
- **Cô lập core agent:** agent có quyền shell và đọc nội dung do người dùng viết (có thể bị prompt-injection). Khi máy chủ chạy
  bằng root và có user hệ thống `gpagent` (Dockerfile tạo sẵn; đổi tên bằng `GP_AGENT_USER`), mỗi job chạy dưới user đó và chỉ
  được trao quyền vào thư mục dự án + HOME của job; `app.db`, khoá phiên, khoá mã hoá, dự án khác đều không đọc được, biến môi
  trường bí mật bị loại. Không có user đó → trang Core agent hiện cảnh báo. Test: `saas/tests/test_hardening.py`.
- Kiểm link nguồn chặn địa chỉ nội bộ (localhost, 10.x, 169.254.x…) ở mọi bước chuyển hướng.
- Văn bản hồ sơ (Jinja trong sections/deck/story) chạy trong **sandbox** — nội dung bị prompt-injection không chạm được Python/OS.
  gen.py/export.py chạy với môi trường đã loại bí mật.
- Lịch sử git của dự án nằm ở `GP_DATA/history/` (ngoài thư mục agent ghi được), tắt hook/fsmonitor. Symlink và file đặc biệt
  agent để lại bị xoá trước mọi lần build; đọc/ghi SSOT, media, gói .zip đều từ chối symlink. `media/` chỉ phục vụ ảnh raster.
- API token chỉ mở các lệnh của agent ngoài (không vào được quản trị, key, token, tài khoản). Body request giới hạn khi đang đọc.
- Hồi quy cho từng lỗ đã tái hiện: `saas/tests/test_security.py`.
- Job chạy bằng key của user dùng HOME tạm, xoá ngay khi job kết thúc. Agent chỉ được ghi trong thư mục dự án (theo prompt
  `pipeline/core-agent-prompt.md`); nên chạy trong container riêng vì agent có quyền shell.

## Mã nguồn

```
saas/server/  config.py (đường dẫn, khoá) · db.py (SQLite) · security.py · llm.py (4 provider BYOK)
              interview.py (phỏng vấn, brainstorm, brief) · agents.py (agy/claude, PTY) · worker.py (hàng đợi job) · main.py (API)
saas/static/  login.html · app.html · admin.html · gp.css · gp.js
pipeline/     interview.yaml (bộ câu hỏi chuẩn) · core-agent-prompt.md · playbook.yaml · stages.yaml
```

## Bản demo trên claude.ai

`python saas/demo/build.py <thư-mục>` ghép login/app/admin thành một trang chạy hoàn toàn trong trình duyệt:
`saas/demo/mock.js` giả lập cùng API (dữ liệu trong localStorage), trợ lý phỏng vấn/brainstorm gọi Claude của người xem
(capability `sample`), core agent chỉ **mô phỏng** (CLI thật cần máy chủ). Dự án mẫu AI Robot Pet có hồ sơ và file tải về thật.
Publish thư mục đó làm artifact với `capabilities: {sample: {}, downloads: true}`.
