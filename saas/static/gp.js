// Tiện ích dùng chung: gọi API (luôn kèm X-GP chống CSRF), escape, markdown an toàn, toast.
const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
async function api(path, opt = {}) {
  const r = await fetch("/api" + path, {method: opt.method || (opt.body ? "POST" : "GET"), credentials: "same-origin",
    headers: {"X-GP": "1", ...(opt.body ? {"Content-Type": "application/json"} : {})}, body: opt.body ? JSON.stringify(opt.body) : undefined});
  if (r.status === 401 && !path.startsWith("/auth")) { location.href = "/login"; throw new Error("401"); }
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof j.detail === "string" ? j.detail : `Lỗi ${r.status}`);
  return j;
}
// Không có DOMPurify (CDN lỗi/bị chặn) thì KHÔNG trả HTML thô — hiện chữ thuần, an toàn hơn đẹp.
function md(s) { return window.marked && window.DOMPurify ? DOMPurify.sanitize(marked.parse(String(s || ""), {breaks: true})) : esc(s).replace(/\n/g, "<br>"); }
let _tt; function toast(t) { let e = $(".toast"); if (!e) { e = document.createElement("div"); e.className = "toast"; document.body.append(e); }
  e.textContent = t; e.hidden = false; clearTimeout(_tt); _tt = setTimeout(() => e.hidden = true, 3200); }
// ---- Định dạng: mọi số / ngày trên UI đi qua đây (vi-VN).
const fmt = n => (n ?? 0).toLocaleString("vi-VN");
const fmtDate = iso => iso ? new Date(iso).toLocaleString("vi-VN", {day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit"}) : "—";
const fmtDay = iso => iso ? new Date(iso).toLocaleDateString("vi-VN", {day: "2-digit", month: "2-digit"}) : "—";
const ago = iso => { if (!iso) return "—"; const s = (Date.now() - new Date(iso)) / 1000;
  return s < 60 ? "vừa xong" : s < 3600 ? Math.floor(s / 60) + " phút trước" : s < 86400 ? Math.floor(s / 3600) + " giờ trước"
    : s < 7 * 86400 ? Math.floor(s / 86400) + " ngày trước" : new Date(iso).toLocaleDateString("vi-VN"); };
const when = iso => iso ? `<time datetime="${esc(iso)}" title="${esc(fmtDate(iso))}">${esc(ago(iso))}</time>` : "—";   // tương đối + giờ chính xác khi rê chuột
const fmtCompact = n => { n = Number(n || 0); return n >= 1e9 ? (n / 1e9).toLocaleString("vi-VN", {maximumFractionDigits: 1}) + " tỷ"
  : n >= 1e6 ? (n / 1e6).toLocaleString("vi-VN", {maximumFractionDigits: 1}) + " triệu" : n >= 1e4 ? Math.round(n / 1e3).toLocaleString("vi-VN") + " nghìn" : fmt(n); };
const fmtUSD = n => n ? "$" + Number(n).toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2}) : "—";
// Giao diện Sáng/Tối/Theo hệ thống: lưu theo tài khoản (prefs.theme) + localStorage để áp ngay khi tải trang, không nháy màu.
function applyTheme(t) {
  try { localStorage.setItem("gp-theme", t || "system"); } catch (e) { /* trình duyệt chặn bộ nhớ: vẫn áp cho phiên này */ }
  if (t === "light" || t === "dark") document.documentElement.dataset.theme = t; else delete document.documentElement.dataset.theme;
}
try { const t = localStorage.getItem("gp-theme"); if (t) applyTheme(t); } catch (e) { /* không có localStorage */ }
const fmtInt = n => Number(n || 0).toLocaleString("vi-VN");

// ---- Thuật ngữ dùng chung (một nơi duy nhất — app và admin nói cùng một thứ tiếng).
const STATUS = {interview: "phỏng vấn", brainstorm: "brainstorm", ready: "sẵn sàng", running: "đang chạy", done: "hoàn thành", failed: "lỗi",
  queued: "đang chờ", starting: "khởi động", cancelled: "đã huỷ", proposed: "đề xuất", locked: "đã chốt", rejected: "đã loại",
  ok: "ổn", active: "hoạt động", disabled: "đã khoá", off: "đã tắt", new: "mới", not_installed: "chưa cài", error: "lỗi", quota_exhausted: "hết quota",
  needs_login: "cần đăng nhập", waiting: "chờ agent", open: "đang mở", used: "đã dùng", expired: "hết hạn", revoked: "đã thu hồi", archived: "đã lưu trữ",
  owner: "chủ hệ thống", admin: "admin", user: "người dùng", maintenance: "bảo trì"};
const ROLE = {owner: "Chủ hệ thống (owner)", admin: "Admin", user: "Người dùng"};
const ENGINE = {agy: "Antigravity", claude: "Claude Code", native: "Engine API", external: "Agent ngoài", demo: "Demo", local: "Máy chủ"};
const BILL = {owner: "tài khoản hệ thống", user_key: "key của người dùng", external: "agent ngoài", demo: "demo", none: "—"};
const pill = s => `<span class="pill ${esc(s)}">${esc(STATUS[s] || s || "—")}</span>`;

// ---- Icon: một bộ SVG nét mảnh, theo màu chữ (không emoji).
const ICONS = {
  home: "M3 10.5 12 3l9 7.5V21h-6v-6H9v6H3z", plus: "M12 5v14M5 12h14", folder: "M3 6h6l2 2h10v11H3z", gear: "M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7zM19.4 13a7.6 7.6 0 0 0 0-2l2-1.6-2-3.4-2.4 1a7 7 0 0 0-1.7-1L15 3.5h-4l-.4 2.5a7 7 0 0 0-1.7 1l-2.4-1-2 3.4L6.6 11a7.6 7.6 0 0 0 0 2l-2 1.6 2 3.4 2.4-1a7 7 0 0 0 1.7 1l.4 2.5h4l.4-2.5a7 7 0 0 0 1.7-1l2.4 1 2-3.4z",
  shield: "M12 3 4 6v6c0 4.5 3.4 8.3 8 9 4.6-.7 8-4.5 8-9V6z", gauge: "M4 18a8 8 0 1 1 16 0M12 18l4-6", users: "M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM2 21v-1a6 6 0 0 1 12 0v1M16 3.5a4 4 0 0 1 0 7.5M22 21v-1a6 6 0 0 0-4-5.6",
  list: "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01", cpu: "M7 7h10v10H7zM9 1v3M15 1v3M9 20v3M15 20v3M1 9h3M1 15h3M20 9h3M20 15h3", chart: "M4 20V10M10 20V4M16 20v-7M22 20H2",
  sliders: "M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0M14 4v4M8 10v4M16 16v4", log: "M6 3h9l4 4v14H6zM14 3v5h5M9 13h7M9 17h7", download: "M12 3v12M6 11l6 6 6-6M4 21h16",
  share: "M14 4h6v6M20 4 10 14M18 14v6H4V6h6", external: "M14 4h6v6M20 4 10 14M18 14v6H4V6h6", play: "M6 4l14 8-14 8z", more: "M5 12h.01M12 12h.01M19 12h.01", menu: "M4 6h16M4 12h16M4 18h16",
  refresh: "M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7", check: "M5 12l5 5L20 7", x: "M6 6l12 12M18 6 6 18", search: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM21 21l-5-5"};
const icon = (n, cls = "") => `<svg class="ic ${cls}" viewBox="0 0 24 24" aria-hidden="true"><path d="${ICONS[n] || ""}"/></svg>`;

// ---- Khung trang dùng chung: tiêu đề + mô tả + nút chính góc phải (+ phần dưới, vd tab của dự án).
function topbar(title, sub = "", actions = "", below = "") {
  return `<div class="top">${globalBanner(window.ME)}<div class="row"><button class="burger ghost sm" type="button" aria-label="Mở menu">${icon("menu")}</button>
    <div class="grow"><h1>${title}</h1>${sub ? `<div class="sub">${sub}</div>` : ""}</div>${actions ? `<div class="top-actions">${actions}</div>` : ""}</div>${below}</div>`;
}
const loading = (t = "Đang tải…") => `<div class="loading"><span class="spinner"></span> ${esc(t)}</div>`;
// Hướng dẫn lấy key từng bước (dữ liệu từ server: llm.GUIDES, search.GUIDES)
const guideBox = (g, title = "Cách lấy key") => !g ? "" : `<div class="guide"><div class="row"><b class="grow">${esc(title)}</b>${g.tag ? `<span class="pill core">${esc(g.tag)}</span>` : ""}</div>
  <ol>${g.steps.map(s => `<li>${esc(s)}</li>`).join("")}</ol>
  <a class="btn" href="${esc(g.url)}" target="_blank" rel="noopener noreferrer">${icon("external")}${esc(g.url_label)}</a>${g.cost ? `<p class="hint" style="margin:8px 0 0">${esc(g.cost)}</p>` : ""}</div>`;
const emptyRow = (cols, text, action = "") => `<tr class="empty-row"><td colspan="${cols}"><div class="empty">${text}${action ? `<div style="margin-top:10px">${action}</div>` : ""}</div></td></tr>`;
const loadError = (msg, retry) => `<div class="banner bad">${esc(msg)} <button type="button" class="sm" onclick="${retry}">Thử lại</button></div>`;
// Overlay (hộp thoại, ngăn kéo, menu, modal) đóng khi chuyển trang — không để lơ lửng trên trang mới.
function closeOverlays() { $$(".modal, .menu, .drawer, .drawer-bg").forEach(e => e.remove()); }
window.addEventListener("hashchange", closeOverlays);
async function logout() { await api("/auth/logout", {method: "POST"}); location.href = "/login"; }
document.addEventListener("click", e => { if (e.target.closest(".burger")) $(".side").classList.toggle("open");
  else if (!e.target.closest(".side") || e.target.closest(".side a[href], .side button:not(.burger)")) $(".side")?.classList.remove("open"); });  // chọn mục → đóng menu trên điện thoại
// Lưới an toàn: lỗi API nào chưa được bắt riêng vẫn hiện cho người dùng (thay vì im lặng như đã lưu).
window.addEventListener("unhandledrejection", e => { toast(e.reason?.message || "Có lỗi xảy ra — thử lại"); e.preventDefault(); });
// Hộp thoại trong trang (thay confirm/prompt — nhiều trình nhúng như claude.ai chặn hộp thoại của trình duyệt).
function dialog({title, body = "", fields = [], ok = "Đồng ý", danger = false}) {
  return new Promise(res => {
    const w = document.createElement("div"); w.className = "modal";
    w.innerHTML = `<form class="card" role="dialog" aria-modal="true" aria-label="${esc(title)}"><h2>${esc(title)}</h2>${body ? `<p class="hint">${esc(body)}</p>` : ""}
      ${fields.map((f, i) => `<label for="dlg${i}">${esc(f.label || "")}</label>${f.multiline ? `<textarea id="dlg${i}" rows="3">${esc(f.value || "")}</textarea>`
        : `<input id="dlg${i}" type="${f.type || "text"}" value="${esc(f.value || "")}" ${f.type === "password" ? 'autocomplete="new-password"' : ""}>`}`).join("")}
      <div class="row" style="margin-top:14px;justify-content:flex-end"><button type="button" class="ghost" data-x>Huỷ</button><button class="${danger ? "danger" : "pri"}">${esc(ok)}</button></div></form>`;
    const done = v => { w.remove(); document.removeEventListener("keydown", key); res(v); };
    const key = e => { if (e.key === "Escape") done(null); };
    w.querySelector("[data-x]").onclick = () => done(null);
    w.onclick = e => { if (e.target === w) done(null); };
    w.querySelector("form").onsubmit = e => { e.preventDefault(); done(fields.map((f, i) => w.querySelector("#dlg" + i).value)); };
    document.addEventListener("keydown", key); document.body.append(w);
    (w.querySelector("input,textarea") || w.querySelector("button.pri,button.danger")).focus();
  });
}
const ask = (title, ok = "Đồng ý", danger = true) => dialog({title, ok, danger}).then(v => v !== null);
const askText = (title, value = "", type = "text") => dialog({title, fields: [{value, type}], ok: "Lưu"}).then(v => v && v[0].trim() ? v[0].trim() : null);
// Menu thả xuống gắn với một nút: items = [[nhãn, hàm, nguy hiểm?] | null (vạch ngăn)]. Esc / bấm ra ngoài để đóng; phím mũi tên để chọn.
function menu(anchor, items) {
  document.querySelector(".menu")?.remove();
  const m = document.createElement("div"); m.className = "menu"; m.setAttribute("role", "menu");
  m.innerHTML = items.map((it, i) => it ? `<button type="button" role="menuitem" data-i="${i}" class="${it[2] ? "danger" : ""}">${esc(it[0])}</button>` : "<hr>").join("");
  document.body.append(m);
  const r = anchor.getBoundingClientRect();
  m.style.top = r.bottom + window.scrollY + 6 + "px";
  m.style.left = Math.max(8, Math.min(r.right - m.offsetWidth, innerWidth - m.offsetWidth - 8)) + window.scrollX + "px";
  const btns = [...m.querySelectorAll("button")]; btns[0]?.focus();
  const close = () => { m.remove(); document.removeEventListener("keydown", key); document.removeEventListener("mousedown", out); anchor.focus(); };
  const key = e => { const i = btns.indexOf(document.activeElement);
    if (e.key === "Escape") close(); else if (e.key === "ArrowDown") { e.preventDefault(); btns[(i + 1) % btns.length].focus(); }
    else if (e.key === "ArrowUp") { e.preventDefault(); btns[(i - 1 + btns.length) % btns.length].focus(); } };
  const out = e => { if (!m.contains(e.target) && e.target !== anchor) close(); };
  btns.forEach(b => b.onclick = () => { close(); items[+b.dataset.i][1](); });
  document.addEventListener("keydown", key); setTimeout(() => document.addEventListener("mousedown", out), 0);
}
// Dải thông báo toàn hệ thống (owner đặt ở Cài đặt → Vận hành) + trạng thái bảo trì — hiện ở đầu mọi trang.
function globalBanner(me) {
  if (!me) return "";
  const parts = [me.maintenance && "<b>Đang bảo trì</b> — tạm thời chỉ xem được, chưa tạo/chạy/sửa.", me.announcement && esc(me.announcement)].filter(Boolean);
  return parts.length ? `<div class="gbanner ${me.maintenance || me.announcement_level === "warn" ? "warn" : ""}" role="status">${parts.join(" ")}${me.support_email ? ` <span class="hint">Hỗ trợ: <a href="mailto:${esc(me.support_email)}">${esc(me.support_email)}</a></span>` : ""}</div>` : "";
}
