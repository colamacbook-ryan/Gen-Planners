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

Biến môi trường: `GP_DATA` (mặc định `saas/data/`, đã gitignore), `GP_COOKIE_SECURE=1` khi chạy sau HTTPS,
`GP_SESSION_SECRET` / `GP_FERNET_KEY` nếu muốn quản lý khoá ngoài file. **Sao lưu `GP_DATA/fernet.key`** — mất file này là
mất mọi API key đã lưu.

Kiểm thử: `GP_DATA=$(mktemp -d) python -m pytest saas/tests -q` (luồng đầy đủ: phân quyền, phỏng vấn, brainstorm, brief,
job demo, hồ sơ, admin, khoá tài khoản).

## Bảo mật

- Mật khẩu scrypt; phiên là cookie ký (HttpOnly, SameSite=Lax), khoá tài khoản hay đổi mật khẩu làm phiên cũ mất hiệu lực.
- Mọi lệnh ghi cần header `X-GP` (chặn CSRF từ form chéo site). Đăng nhập giới hạn 10 lần / 5 phút / IP.
- Dữ liệu dự án cô lập theo user; admin chỉ đọc. Trang Core agent và Cài đặt chỉ owner.
- Job chạy bằng key của user dùng HOME tạm, xoá ngay khi job kết thúc. Agent chỉ được ghi trong thư mục dự án (theo prompt
  `pipeline/core-agent-prompt.md`); nên chạy trong container riêng vì agent có quyền shell.

## Mã nguồn

```
saas/server/  config.py (đường dẫn, khoá) · db.py (SQLite) · security.py · llm.py (4 provider BYOK)
              interview.py (phỏng vấn, brainstorm, brief) · agents.py (agy/claude, PTY) · worker.py (hàng đợi job) · main.py (API)
saas/static/  login.html · app.html · admin.html · gp.css · gp.js
pipeline/     interview.yaml (bộ câu hỏi chuẩn) · core-agent-prompt.md · playbook.yaml · stages.yaml
```
