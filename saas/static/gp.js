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
const fmt = n => (n ?? 0).toLocaleString("vi-VN");
const ago = iso => { if (!iso) return "—"; const s = (Date.now() - new Date(iso)) / 1000;
  return s < 60 ? "vừa xong" : s < 3600 ? Math.floor(s / 60) + " phút trước" : s < 86400 ? Math.floor(s / 3600) + " giờ trước" : new Date(iso).toLocaleDateString("vi-VN"); };
// Giao diện Sáng/Tối/Theo hệ thống: lưu theo tài khoản (prefs.theme) + localStorage để áp ngay khi tải trang, không nháy màu.
function applyTheme(t) {
  try { localStorage.setItem("gp-theme", t || "system"); } catch (e) { /* trình duyệt chặn bộ nhớ: vẫn áp cho phiên này */ }
  if (t === "light" || t === "dark") document.documentElement.dataset.theme = t; else delete document.documentElement.dataset.theme;
}
try { const t = localStorage.getItem("gp-theme"); if (t) applyTheme(t); } catch (e) { /* không có localStorage */ }
const fmtInt = n => Number(n || 0).toLocaleString("vi-VN");
const STATUS = {interview: "phỏng vấn", brainstorm: "brainstorm", ready: "sẵn sàng chạy", running: "đang chạy", done: "hoàn thành", failed: "lỗi",
  queued: "chờ", starting: "khởi động", cancelled: "đã huỷ", proposed: "đề xuất", locked: "đã chốt", rejected: "đã loại",
  ok: "ổn", active: "hoạt động", disabled: "khoá", new: "mới", not_installed: "chưa cài", error: "lỗi", quota_exhausted: "hết quota", needs_login: "cần đăng nhập", waiting: "chờ agent"};
const pill = s => `<span class="pill ${esc(s)}">${esc(STATUS[s] || s || "—")}</span>`;
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
