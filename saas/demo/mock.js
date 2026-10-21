// Gen Planner — backend giả lập trong trình duyệt cho bản demo trên claude.ai.
// Cùng API với saas/server/main.py; dữ liệu nằm trong localStorage của người xem.
// Trợ lý phỏng vấn/brainstorm dùng Claude thật qua capability `sample` (tài khoản Claude của người xem);
// core agent (agy/claude CLI) chỉ được MÔ PHỎNG — CLI thật cần máy chủ.
(() => {
const BANK = __BANK__;
const PROVIDERS = {
  anthropic: {label: "Anthropic (Claude)", models: ["claude-sonnet-5-5", "claude-opus-5-5", "claude-haiku-5-5"], plan_engine: "claude"},
  openai: {label: "OpenAI", models: [], plan_engine: null},
  gemini: {label: "Google Gemini", models: ["gemini-2.5-pro", "gemini-2.5-flash"], plan_engine: "agy"},
  openrouter: {label: "OpenRouter", models: [], plan_engine: null}};
const ENGINES = {
  agy: {label: "Antigravity CLI (agy)", install: "curl -fsSL https://antigravity.google/cli/install.sh | bash", key_label: "Gemini API key", actions: ["login", "usage", "credits", "logout"]},
  claude: {label: "Claude Code CLI", install: "npm install -g @anthropic-ai/claude-code", key_label: "Anthropic API key", actions: ["login", "usage", "logout"]},
  demo: {label: "Demo (không gọi AI — chỉ build template)", install: "", key_label: null, actions: []}};
const QUESTIONS = BANK.questions, QIDS = QUESTIONS.map(q => q.id), QMAP = Object.fromEntries(QUESTIONS.map(q => [q.id, q]));
const BLOCKS = Object.fromEntries(BANK.blocks.map(b => [b.id, b.title]));
const CATEGORIES = ["product", "customer", "channel", "revenue", "ops", "team", "risk", "roadmap", "other"];
const SAMPLE_SLUG = "ai-robot-pet-mau";
const KEY = "gp-demo-v1";
const DEFAULT_SETTINGS = {site_name: "Gen Planner", allow_signup: "1", plan_billing: "either", default_quota_projects: "5",
  default_quota_jobs_month: "3", job_timeout_min: "120", max_concurrent_jobs: "1", auto_failover: "1", allow_demo_engine: "1",
  google_client_id: "", public_base_url: ""};

// ------------------------------------------------------------------ storage
let D;
const blank = () => ({seq: 1, users: [], session: null, keys: [], projects: [], messages: [], interview: {}, decisions: [],
  profiles: [], jobs: [], usage: [], settings: {...DEFAULT_SETTINGS}, audit: [], terminals: {}});
function load() { try { D = JSON.parse(localStorage.getItem(KEY)) || blank(); } catch { D = blank(); } for (const k of ["shares", "invites", "changes"]) D[k] ??= []; }
function save() { try { localStorage.setItem(KEY, JSON.stringify(D)); } catch {} }
load();
const now = () => new Date().toISOString().replace(/\.\d+Z$/, "Z");
const nid = () => D.seq++;
const month = () => now().slice(0, 7) + "-01";
class HttpErr extends Error { constructor(s, m) { super(m); this.status = s; } }
const fail = (s, m) => { throw new HttpErr(s, m); };
const audit = (uid, action, target = "", detail = null) => D.audit.push({id: nid(), user_id: uid, action, target: String(target), detail: detail ? JSON.stringify(detail) : null, created: now()});
const S = k => D.settings[k] ?? DEFAULT_SETTINGS[k] ?? "";

// ------------------------------------------------------------------ AI (Claude của người xem)
let samplePromise = null;
const getSample = () => samplePromise ??= (window.claude?.use ? window.claude.use("sample").catch(() => null) : Promise.resolve(null));
let aiOff = false;
async function ai(prompt) {
  const sample = aiOff ? null : await getSample();
  if (!sample) return null;
  try { return await sample.json(prompt, {cache: false}); }
  catch (e) {
    if (["not_granted", "sampling_disabled", "not_declared", "capability_disabled", "capability_removed"].includes(e.code)) { aiOff = true; return null; }
    if (e.code === "rate_limited") fail(429, "Claude đang giới hạn lượt gọi — thử lại sau ít phút.");
    if (e.code === "invalid_json") return {reply: e.text || "…"};
    fail(502, "Claude chưa trả lời được (" + e.code + "). Bấm gửi lại.");
  }
}

// ------------------------------------------------------------------ users & auth
const me = () => { const u = D.users.find(u => u.id === D.session); return u && u.status === "active" ? u : null; };
function need() { const u = me(); if (!u) fail(401, "Chưa đăng nhập"); return u; }
function needAdmin() { const u = need(); if (!["owner", "admin"].includes(u.role)) fail(403, "Cần quyền admin"); return u; }
function needOwner() { const u = need(); if (u.role !== "owner") fail(403, "Chỉ owner hệ thống"); return u; }
const pub = u => ({id: u.id, email: u.email, name: u.name, role: u.role, status: u.status, created: u.created, last_login: u.last_login});
function quota(u) {
  const used = D.jobs.filter(j => j.user_id === u.id && j.billing === "owner" && j.engine !== "demo" && j.created >= month() && ["queued", "starting", "running", "done"].includes(j.status)).length;
  const projects = D.projects.filter(p => p.user_id === u.id).length;
  const lp = u.quota_projects ?? +S("default_quota_projects"), lj = u.quota_jobs_month ?? +S("default_quota_jobs_month");
  const unl = ["owner", "admin"].includes(u.role);
  return {projects, projects_limit: unl ? null : lp, owner_jobs_month: used, owner_jobs_limit: unl ? null : lj};
}
function validInvite(token, email) {
  const i = D.invites.find(i => i.token === token);
  if (!i || i.revoked || i.used_by || (i.expires && i.expires < now())) fail(400, "Lời mời không còn hiệu lực. Xin admin gửi lời mời mới.");
  if (email && i.email && i.email !== email) fail(400, `Lời mời này dành cho ${i.email}.`);
  return i;
}
function createUser(email, name, pw, inv) {
  const first = D.users.length === 0;
  if (!first && !inv && S("allow_signup") !== "1") fail(403, "Hệ thống đang tắt đăng ký mới — cần lời mời từ admin.");
  const u = {id: nid(), email, name: name || email.split("@")[0], pw: hashish(pw), role: first ? "owner" : inv ? inv.role : "user", status: "active",
    quota_projects: inv?.quota_projects ?? null, quota_jobs_month: inv?.quota_jobs_month ?? null, invited_by: inv?.created_by ?? null, onboarding: {}, created: now(), last_login: now()};
  if (inv) { inv.used_by = u.id; inv.used_at = now(); }
  D.users.push(u); audit(u.id, "signup", email, {role: u.role});
  if (first) seedSample(u);
  return u;
}
// Bản demo không có máy chủ: mật khẩu chỉ băm nhẹ để không lưu nguyên văn trong localStorage.
function hashish(s) { let h = 2166136261; for (const c of String(s)) { h ^= c.charCodeAt(0); h = Math.imul(h, 16777619); } return (h >>> 0).toString(36) + String(s).length; }

// ------------------------------------------------------------------ projects / interview
function istate(pid) { return D.interview[pid] ??= {answers: {}, current_qid: QIDS[0], done: false}; }
function progress(a) { return {answered: QIDS.filter(q => a[q]).length, total: QIDS.length, required_missing: QIDS.filter(q => QMAP[q].required && !a[q])}; }
function nextUnanswered(a, after) { const i = QIDS.indexOf(after); const order = i >= 0 ? [...QIDS.slice(i + 1), ...QIDS] : QIDS; return order.find(q => !a[q]) ?? null; }
const askText = qid => { const q = QMAP[qid]; return `**${BLOCKS[q.block]} · câu ${QIDS.indexOf(qid) + 1}/${QIDS.length}** — ${q.ask}`; };
const addMsg = (pid, room, role, content, meta) => { const m = {id: nid(), project_id: pid, room, role, content, meta: meta ? JSON.stringify(meta) : null, created: now()}; D.messages.push(m); return m.id; };
function history(pid, room, limit = 24) {
  const ms = D.messages.filter(m => m.project_id === pid && m.room === room).slice(-limit).map(m => ({role: m.role, content: m.content}));
  while (ms.length && ms[0].role !== "user") ms.shift();
  return ms;
}
function slugify(name) {
  const s = name.replace(/[đĐ]/g, "d").normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 40) || "du-an";
  return s + "-" + Math.random().toString(16).slice(2, 6);
}
function getProject(slug, u, write) {
  const p = D.projects.find(p => p.slug === slug); if (!p) fail(404, "Không có dự án");
  if (p.user_id !== u.id && (write || (!["owner", "admin"].includes(u.role) && !p.is_sample))) fail(403, "Không phải dự án của bạn");
  return p;
}
function onboarding(u) {
  const ob = u.onboarding || {}, ps = D.projects.filter(p => p.user_id === u.id && !p.is_sample), ids = new Set(ps.map(p => p.id));
  const steps = [["sample", "Xem một bộ hồ sơ mẫu hoàn chỉnh", !!ob.viewed_sample], ["key", "Thêm API key AI của bạn", D.keys.some(k => k.user_id === u.id)],
    ["project", "Tạo dự án đầu tiên", ps.length > 0], ["interview", `Trả lời đủ ${QUESTIONS.filter(q => q.required).length} câu phỏng vấn bắt buộc`, ps.some(p => !progress(istate(p.id).answers).required_missing.length)],
    ["locked", "Chốt ít nhất một điểm ở Brainstorm", D.decisions.some(d => ids.has(d.project_id) && d.status === "locked")],
    ["plan", "Chạy Plan và xem hồ sơ", D.jobs.some(j => ids.has(j.project_id) && j.kind === "plan" && j.status === "done")],
    ["share", "Gửi link hồ sơ cho nhà đầu tư", D.shares.some(x => ids.has(x.project_id))]];
  return {steps: steps.map(([id, title, done]) => ({id, title, done})), done: steps.filter(x => x[2]).length, total: steps.length, dismissed: !!ob.dismissed};
}
let exportCache = {};
async function exportJson(p, part) {
  const id = p.is_sample ? "ai-robot-pet" : "mau-template", k = id + part;
  return exportCache[k] ??= await (await realFetch(`data/projects/${id}/export/${part}.json`)).json();
}
function summary(p) {
  const j = [...D.jobs].reverse().find(j => j.project_id === p.id);
  return {id: p.id, slug: p.slug, name: p.name, country: p.country, status: p.status, created: p.created, updated: p.updated, is_sample: p.is_sample ? 1 : 0,
    progress: progress(istate(p.id).answers), last_job: j ? {id: j.id, status: j.status, engine: j.engine, billing: j.billing, created: j.created, finished: j.finished, error: j.error} : null,
    exported: !!p.exported, locked: D.decisions.filter(d => d.project_id === p.id && d.status === "locked").length};
}
function startInterview(p) {
  const st = istate(p.id);
  addMsg(p.id, "interview", "assistant", `Chào anh/chị — tôi là trợ lý phỏng vấn của **${p.name}**. Tôi sẽ hỏi ${QIDS.length} câu ngắn theo ${Object.keys(BLOCKS).length} chủ đề để hiểu đúng ý tưởng gốc trước khi agent nghiên cứu. Câu nào chưa biết, cứ nói "chưa biết" — agent sẽ nghiên cứu sau.\n\n` + askText(st.current_qid), {qid: st.current_qid});
}
function estTokens(pid, uid, prompt, out) {
  D.usage.push({id: nid(), user_id: uid, project_id: pid, source: "chat", provider: "claude.ai", model: "Claude (sample)",
    input_tokens: Math.round(prompt.length / 4), output_tokens: Math.round(JSON.stringify(out || "").length / 4), created: now()});
}
async function interviewTurn(p, u, text) {
  const st = istate(p.id), a = st.answers, cur = st.current_qid;
  addMsg(p.id, "interview", "user", text, {qid: cur}); save();
  const hist = history(p.id, "interview").map(m => (m.role === "user" ? "Founder: " : "Bạn: ") + m.content).join("\n\n");
  const prompt = "Bạn là chuyên gia phỏng vấn founder (venture analyst cấp cao). Mục tiêu: hiểu đúng ý tưởng gốc để agent nghiên cứu sau đó.\nQuy tắc:\n- " +
    BANK.style.join("\n- ") + `\n\nÝ tưởng gốc:\n${p.idea}\n\nDanh sách câu hỏi (id | chủ đề | câu hỏi | probes | đã trả lời):\n` +
    QUESTIONS.map(q => `${q.id} | ${BLOCKS[q.block]} | ${q.ask} | ${(q.probes || []).join("; ")} | ${a[q.id] || "—"}`).join("\n") +
    `\n\nCâu đang hỏi: ${cur}.\n\nHội thoại gần đây:\n${hist}\n\n` +
    'Trả về DUY NHẤT một JSON: {"captured": {"<id>": "tóm tắt câu trả lời bằng lời của founder, giữ nguyên tên gọi và con số"}, "next_qid": "<id câu sẽ hỏi tiếp, hoặc giữ id hiện tại nếu cần probe>", "reply": "lời nói tiếp theo với founder bằng tiếng Việt (ghi nhận ngắn + đúng một câu hỏi, markdown)", "done": false}. Founder trả lời luôn cho câu khác thì capture cả câu đó. Khi mọi câu đã có trả lời: done=true và reply tóm tắt 5 dòng.';
  let out = await ai(prompt), provider = "claude.ai";
  if (!out) {
    provider = "demo";
    if (cur) a[cur] = text.trim();
    const nxt = nextUnanswered(a, cur);
    out = {captured: {}, next_qid: nxt, done: !nxt, reply: "Đã ghi nhận." + (nxt ? "\n\n" + askText(nxt) : "\n\nĐã đủ các câu. Mở tab **Brief** để xem bản tổng hợp, hoặc sang **Brainstorm** để chốt các điểm quan trọng.")};
  } else estTokens(p.id, u.id, prompt, out);
  for (const [k, v] of Object.entries(out.captured || {})) if (QMAP[k] && String(v).trim()) a[k] = String(v).trim();
  const nxt = QMAP[out.next_qid] ? out.next_qid : nextUnanswered(a, cur);
  st.current_qid = nxt; st.done = !!out.done || !nxt;
  const reply = out.reply || (nxt ? askText(nxt) : "Đã đủ thông tin.");
  addMsg(p.id, "interview", "assistant", reply, {qid: nxt, provider});
  p.updated = now();
  return {reply, progress: progress(a), current_qid: nxt, done: st.done};
}
async function brainstormTurn(p, u, text) {
  const mid = addMsg(p.id, "brainstorm", "user", text); save();
  const decs = D.decisions.filter(d => d.project_id === p.id && d.status !== "rejected"), a = istate(p.id).answers;
  const hist = history(p.id, "brainstorm", 16).map(m => (m.role === "user" ? "Founder: " : "Cố vấn: ") + m.content).join("\n\n");
  const prompt = "Bạn là cố vấn chiến lược cấp cao, cùng founder brainstorm để CHỐT DẦN các điểm quan trọng của dự án.\n" +
    "Tôn trọng ý tưởng gốc và các mại điểm founder giữ (must_keep); đề xuất làm nó mạnh lên, không thay hướng. Nói thẳng trade-off, hỏi lại khi thiếu dữ kiện, không bịa số liệu hay nguồn. MỌI con số thị trường chưa có nguồn phải ghi ngay sau nó “(ước tính, cần kiểm chứng)”.\n\n" +
    `Ý tưởng gốc:\n${p.idea}\n\nTrả lời phỏng vấn:\n` + (Object.entries(a).map(([k, v]) => `- ${QMAP[k]?.ask} → ${v}`).join("\n") || "- chưa có") +
    "\n\nCác điểm (status):\n" + (decs.map(d => `- #${d.id} [${d.status}] (${d.category}) ${d.title}: ${d.detail || ""}`).join("\n") || "- chưa có") +
    `\n\nHội thoại:\n${hist}\n\n` +
    `Trả về DUY NHẤT một JSON: {"reply": "câu trả lời markdown tiếng Việt, ngắn gọn, có lập luận", "proposals": [{"title": "điểm cần chốt, ≤ 12 từ", "detail": "1–3 câu: nội dung + vì sao", "category": "một trong ${CATEGORIES.join("|")}"}]}. Chỉ đưa proposal khi thật sự có điểm đáng chốt (0–3 cái), không lặp điểm đã có.`;
  let out = await ai(prompt), provider = "claude.ai";
  if (!out) { provider = "demo"; out = {reply: "(Chế độ demo — chưa bật Claude) Tôi ghi ý này thành một điểm đề xuất để anh/chị chốt hoặc loại.", proposals: text.trim().length > 15 ? [{title: text.trim().slice(0, 80), detail: text.trim(), category: "other"}] : []}; }
  else estTokens(p.id, u.id, prompt, out);
  const created = [];
  for (const pr of (out.proposals || []).slice(0, 3)) {
    if (!String(pr.title || "").trim()) continue;
    const d = {id: nid(), project_id: p.id, title: String(pr.title).trim().slice(0, 200), detail: String(pr.detail || "").trim(),
      category: CATEGORIES.includes(pr.category) ? pr.category : "other", status: "proposed", source_msg: mid, created: now(), updated: now()};
    D.decisions.push(d); created.push(d.id);
  }
  const reply = out.reply || "…";
  addMsg(p.id, "brainstorm", "assistant", reply, {proposals: created, provider}); p.updated = now();
  return {reply, proposals: created};
}
function buildBrief(p) {
  const a = istate(p.id).answers, decs = D.decisions.filter(d => d.project_id === p.id);
  const L = [`# Brief — ${p.name}`, "", '> Biên dịch tự động từ phòng phỏng vấn + phòng brainstorm. Đây là neo **founder-first**: agent phải giữ ý tưởng gốc và các điểm đã chốt làm trung tâm; đề xuất khác chỉ ghi ở mục "Phương án khác".', "",
    `Thị trường mục tiêu: ${p.country || "Việt Nam"}`, "", "## Ý tưởng gốc (nguyên văn)", "", p.idea || "", "", "## Phỏng vấn founder", ""];
  for (const [bid, title] of Object.entries(BLOCKS)) { const qs = QUESTIONS.filter(q => q.block === bid && a[q.id]); if (qs.length) L.push(`### ${title}`, "", ...qs.map(q => `- **${q.ask}**  \n  ${a[q.id]}`), ""); }
  const locked = decs.filter(d => d.status === "locked");
  L.push("## Các điểm đã chốt", "", ...(locked.length ? locked.map(d => `- **[${d.category}] ${d.title}** — ${d.detail || ""}`) : ["- (chưa có)"]), "");
  const rej = decs.filter(d => d.status === "rejected"); if (rej.length) L.push("## Hướng đã loại (không đi theo)", "", ...rej.map(d => `- ${d.title}`), "");
  const open = QUESTIONS.filter(q => !a[q.id]), pend = decs.filter(d => d.status === "proposed");
  L.push("## Câu hỏi mở — agent nghiên cứu hoặc ghi là giả định", "", ...open.map(q => `- ${q.ask}${q.required ? " (bắt buộc)" : ""}`), ...pend.map(d => `- Điểm chưa chốt: ${d.title}`));
  if (!open.length && !pend.length) L.push("- (không có)");
  p.brief_md = L.join("\n") + "\n"; p.updated = now();
  return p.brief_md;
}
function seedSample(owner) {
  if (D.projects.some(p => p.slug === SAMPLE_SLUG)) return;
  const p = {id: nid(), slug: SAMPLE_SLUG, user_id: owner.id, name: "Hệ sinh thái AI Robot Pet Việt (mẫu)", country: "Việt Nam", status: "done", exported: true, is_sample: 1,
    idea: "Pet AI tháo rời não–thân mang thương hiệu Việt, OEM từ Trung Quốc, lắp ráp và server tại Việt Nam; chuỗi CLB robotics để chơi, mua, F&B; lớp huấn luyện prompt và lập trình pet; thi đấu có giải; dịch vụ sửa chữa, nâng cấp, trang trí; rồi nhượng quyền.",
    created: now(), updated: now(), brief_md: null};
  D.projects.push(p); startInterview(p);
  D.jobs.push({id: nid(), kind: "plan", project_id: p.id, user_id: owner.id, engine: "claude", billing: "owner", model: null, status: "done", attempt: 1,
    log: "Hồ sơ mẫu dựng từ repo Gen-Planners (projects/ai-robot-pet): 7 hướng nghiên cứu, 46 nguồn có URL, build + check 0 lỗi.\n— kết thúc: done\n", usage: null, error: null, created: now(), started: now(), finished: now()});
}

// ------------------------------------------------------------------ jobs (mô phỏng)
const timers = {};
function log(j, t) { j.log += t + "\n"; }
function simulate(jid) {
  const j = D.jobs.find(x => x.id === jid); if (!j) return;
  const p = D.projects.find(x => x.id === j.project_id);
  const prof = D.profiles.find(x => x.id === j.profile_id);
  const steps = [];
  if (j.kind === "install") {
    steps.push("$ bash -lc " + ENGINES[j.engine].install, "[mô phỏng] Bản demo không có máy chủ để cài CLI.", "Trên máy chủ thật, nút này đã cài agy 1.4.3: tải manifest → kiểm sha512 → /root/.local/bin/agy.");
  } else if (j.engine === "demo") {
    steps.push("Engine demo: không gọi AI — ghi idea.md + brief.md vào dự án và build từ template để thử luồng.", `$ python gen.py new ${p.slug}`, `✓ tạo ${p.slug}`, `$ python gen.py build ${p.slug}`, "✓ build business-plan.md · deck.md · financials.xlsx", `$ python gen.py check ${p.slug}`, "✓ check: 0 lỗi, 36 cảnh báo (giả định còn placeholder — chưa nghiên cứu)", `$ python tools/export.py ${p.slug}`, "project.json · dossier.json · documents.json");
  } else {
    const who = j.billing === "user_key" ? `API key của user (${j.key_hint || ""})` : `tài khoản hệ thống "${prof?.name || "?"}"`;
    steps.push(`[MÔ PHỎNG] Engine ${j.engine} · ${who} · model ${j.model || prof?.model || "mặc định"}`,
      "[MÔ PHỎNG] Bản demo trên claude.ai không chạy được CLI agent — đây là trình tự một job thật sẽ đi qua:",
      "› Đọc AGENTS.md, pipeline/playbook.yaml, pipeline/stages.yaml, brief.md",
      ...BANKSTREAMS.map(s => `⚙ ${s}`),
      "› Tổng hợp evidence.yaml, assumptions.yaml, sections/*.md, deck.md, story.yaml, datasets.yaml",
      `$ python gen.py build ${p.slug} && python gen.py check ${p.slug}`, "✓ (mô phỏng) hồ sơ hiển thị bằng template vì không có nghiên cứu thật");
  }
  j.status = "running"; j.started = now(); save();
  let i = 0;
  const tick = () => {
    const jj = D.jobs.find(x => x.id === jid); if (!jj || jj.status === "cancelled") return;
    if (i < steps.length) { log(jj, steps[i++]); save(); timers[jid] = setTimeout(tick, 600 + Math.random() * 500); return; }
    jj.status = "done"; jj.finished = now(); log(jj, "— kết thúc: done"); if (p) { p.status = "done"; p.exported = true; p.updated = now(); }
    save();
  };
  timers[jid] = setTimeout(tick, 500);
}
const BANKSTREAMS = ["R1 Thị trường dẫn đầu & toàn cầu", "R2 Nguồn hàng, chi phí đơn vị, logistics", "R3 Pháp lý, thuế, ưu đãi", "R4 Cầu nội địa & khách hàng",
  "R5 Mô hình so sánh cho từng cấu phần", "R6 Khoảng trống & use-case", "R7 Tín hiệu dài hạn 5–15 năm", "R8 Hình ảnh & clip cấu phần cốt lõi", "R9 Hình ảnh & clip hệ sinh thái"];
function activeProfile(exclude = []) {
  return D.profiles.filter(p => p.enabled && !exclude.includes(p.id) && !["quota_exhausted", "needs_login"].includes(p.status))
    .sort((a, b) => (b.is_active - a.is_active) || (a.priority - b.priority) || (a.id - b.id))[0] || null;
}
// Job đang "running" khi tải lại trang → chạy tiếp mô phỏng
for (const j of D.jobs) if (["queued", "starting", "running"].includes(j.status)) { j.log = ""; simulate(j.id); }

// ------------------------------------------------------------------ terminal (bản ghi thật từ máy chủ)
const AGY_MENU = "▄▀▀▄\n▀▀▀▀▀▀\n▀▀▀▀▀▀▀▀\n  ▄▀▀    ▀▀▄\n ▄▀▀      ▀▀▄\n\n Welcome to the Antigravity CLI. You are currently not signed in.\n\n Select login method:\n > 1. Google OAuth\n   2. Use a Google Cloud project\n\n↑/↓ Navigate · enter Select\n";
function termText(t) { return "[Bản ghi màn hình agy 1.4.3 trên máy chủ thật — bản demo không chạy CLI]\n\n" + t.out; }
function termInput(prof, text) {
  const t = D.terminals[prof.id]; if (!t) fail(400, "Terminal chưa mở");
  if (t.action !== "login") { t.out += "\n" + text; return; }
  if (t.step === 0) { t.step = 1; t.out += "\n ───\n → Click here to authenticate\n ───\n\n If you aren't automatically redirected, paste the authorization code below:\n\n authorization code...\n\n[Trên máy chủ thật: link Google OAuth hiện ở đây — mở nó, đăng nhập, rồi dán mã vào ô nhập.]\n"; }
  else if (text.trim()) { t.out += "\n" + "•".repeat(Math.min(24, text.length)) + "\n✓ [mô phỏng] Đã đăng nhập. Đóng terminal để profile chuyển sang sẵn sàng.\n"; t.alive = false; t.loggedIn = true; }
}

// ------------------------------------------------------------------ router
const routes = [];
const R = (m, re, fn) => routes.push([m, new RegExp("^" + re + "$"), fn]);

R("GET", "/public", (b, m, q) => { let invite = null; if (q.get("invite")) { try { const i = validInvite(q.get("invite")); invite = {email: i.email, role: i.role}; } catch (e) { invite = {error: e.message}; } }
  return {invite, ...PUBLIC()}; });
const PUBLIC = () => ({site_name: S("site_name"), allow_signup: S("allow_signup") === "1", google: false, has_owner: D.users.length > 0, demo: true});
R("POST", "/auth/signup", (b) => {
  const email = String(b.email || "").trim().toLowerCase(), pw = String(b.password || "");
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email) || pw.length < 8) fail(400, "Email không hợp lệ hoặc mật khẩu dưới 8 ký tự.");
  if (D.users.some(u => u.email === email)) fail(409, "Email đã có tài khoản.");
  const u = createUser(email, b.name, pw, b.invite ? validInvite(b.invite, email) : null); D.session = u.id; return {ok: true, role: u.role};
});
R("POST", "/auth/login", (b) => {
  const u = D.users.find(u => u.email === String(b.email || "").trim().toLowerCase());
  if (!u || u.pw !== hashish(b.password || "")) fail(401, "Sai email hoặc mật khẩu.");
  if (u.status !== "active") fail(403, "Tài khoản đang bị khoá.");
  D.session = u.id; u.last_login = now(); audit(u.id, "login", u.email); return {ok: true, role: u.role};
});
R("POST", "/auth/logout", () => { D.session = null; return {ok: true}; });
R("GET", "/me", () => { const u = need(); return {...pub(u), has_keys: D.keys.some(k => k.user_id === u.id), site_name: S("site_name"), plan_billing: S("plan_billing"), quota: quota(u), demo_allowed: S("allow_demo_engine") === "1", ai_live: !aiOff, onboarding: onboarding(u)}; });
R("POST", "/me/onboarding", (b) => { const u = need(); u.onboarding ??= {}; for (const k of ["viewed_sample", "dismissed"]) if (k in b) u.onboarding[k] = !!b[k]; return {ok: true}; });
R("POST", "/me/password", (b) => { const u = need(); if (u.pw !== hashish(b.old || "")) fail(400, "Mật khẩu cũ không đúng"); if (String(b.new || "").length < 8) fail(400, "Mật khẩu mới tối thiểu 8 ký tự"); u.pw = hashish(b.new); audit(u.id, "password_change", u.email); return {ok: true}; });

R("GET", "/tokens", () => (need(), []));
R("GET", "/projects/([\\w-]+)/history", (b, [slug]) => { getProject(slug, need()); return []; });
R("GET", "/projects/([\\w-]+)/lint", (b, [slug]) => { getProject(slug, need());
  return {errors: [], warnings: ["Bản demo không chạy được bộ kiểm tra độ hợp lý (cần Python trên máy chủ). Trên bản máy chủ, mục này liệt kê lỗi và chỗ nhà đầu tư sẽ hỏi."]}; });
R("POST", "/tokens", () => fail(400, "API token cho agent ngoài chỉ có trên bản máy chủ."));
R("GET", "/keys/(\\d+)/models", () => fail(400, "Bản demo không gọi được nhà cung cấp AI để lấy danh sách model."));
R("GET", "/providers", () => (need(), PROVIDERS));
const keyRow = k => ({...k, plan_engine: PROVIDERS[k.provider].plan_engine});
R("GET", "/keys", () => { const u = need(); return D.keys.filter(k => k.user_id === u.id).sort((a, b) => b.is_default - a.is_default).map(keyRow); });
R("POST", "/keys", (b) => {
  const u = need(), key = String(b.key || "").trim();
  if (!PROVIDERS[b.provider] || key.length < 10) fail(400, "Provider hoặc key không hợp lệ");
  const model = String(b.model || PROVIDERS[b.provider].models[0] || "").trim(); if (!model) fail(400, "Provider này cần nhập tên model");
  // Bản demo KHÔNG lưu key: chỉ giữ 4 ký tự đầu/cuối để hiển thị.
  const k = {id: nid(), user_id: u.id, provider: b.provider, label: PROVIDERS[b.provider].label, key_hint: key.length > 12 ? key.slice(0, 4) + "…" + key.slice(-4) : "…",
    model, is_default: D.keys.some(k => k.user_id === u.id) ? 0 : 1, last_test: null, last_test_ok: null, created: now()};
  D.keys.push(k); audit(u.id, "api_key_add", b.provider); return keyRow(k);
});
const myKey = (u, id) => D.keys.find(k => k.id === +id && k.user_id === u.id) || fail(404, "Không có key");
R("PATCH", "/keys/(\\d+)", (b, [id]) => { const u = need(), k = myKey(u, id); if (b.is_default) { D.keys.filter(x => x.user_id === u.id).forEach(x => x.is_default = 0); k.is_default = 1; } if (b.model) k.model = String(b.model).trim(); return keyRow(k); });
R("DELETE", "/keys/(\\d+)", (b, [id]) => { const u = need(); myKey(u, id); D.keys = D.keys.filter(k => k.id !== +id); audit(u.id, "api_key_delete", id); return {ok: true}; });
R("POST", "/keys/(\\d+)/test", (b, [id]) => { const k = myKey(need(), id); k.last_test = now(); k.last_test_ok = 0; return {ok: false, message: "Bản demo không lưu và không gửi key đi đâu. Trên máy chủ thật, nút này gọi thẳng API của nhà cung cấp."}; });

R("GET", "/samples", () => (need(), D.projects.filter(p => p.is_sample).map(summary)));
R("GET", "/projects", () => { const u = need(); return D.projects.filter(p => p.user_id === u.id && !p.is_sample).sort((a, b) => b.updated.localeCompare(a.updated)).map(summary); });
R("POST", "/projects", (b) => {
  const u = need(), name = String(b.name || "").trim(), idea = String(b.idea || "").trim();
  if (!name || idea.length < 20) fail(400, "Cần tên dự án và mô tả ý tưởng (tối thiểu vài câu).");
  const q = quota(u); if (q.projects_limit != null && q.projects >= q.projects_limit) fail(403, `Đã đạt giới hạn ${q.projects_limit} dự án của gói. Liên hệ admin để nâng.`);
  const p = {id: nid(), slug: slugify(name), user_id: u.id, name, idea, country: b.country || "Việt Nam", status: "interview", exported: false, brief_md: null, created: now(), updated: now()};
  D.projects.push(p); startInterview(p); audit(u.id, "project_create", p.slug); return summary(p);
});
R("GET", "/projects/([\\w-]+)", async (b, [slug]) => {
  const u = need(), p = getProject(slug, u), st = istate(p.id), kpi = p.exported ? (await exportJson(p, "project")).kpi : null;
  return {...summary(p), idea: p.idea, brief_md: p.brief_md, answers: st.answers, current_qid: st.current_qid, interview_done: st.done,
    questions: QUESTIONS, blocks: BLOCKS, categories: CATEGORIES,
    decisions: D.decisions.filter(d => d.project_id === p.id).sort((a, b) => ((b.status === "locked") - (a.status === "locked")) || b.id - a.id),
    jobs: D.jobs.filter(j => j.project_id === p.id).sort((a, b) => b.id - a.id).slice(0, 10), mine: p.user_id === u.id,
    kpi, links: null, shares: p.user_id === u.id ? D.shares.filter(x => x.project_id === p.id && !x.revoked).reverse() : [],
    changes: [], has_workspace: !!p.exported};
});
const DEMO_RO = "Bản demo chỉ xem được bảng số liệu — sửa và build lại cần máy chủ thật (Python).";
R("GET", "/projects/([\\w-]+)/assumptions", async (b, [slug]) => {
  const p = getProject(slug, need()); if (!p.exported) fail(404, "Dự án chưa có bộ số liệu — chạy Plan trước.");
  const d = await exportJson(p, "dossier"), k = (await exportJson(p, "project")).kpi;
  return {meta: {start_year: 2027}, kpi: k, readonly: DEMO_RO, assumptions: d.assumptions.map(a => ({...a, source: a.source || [], note: a.note || ""}))};
});
R("PATCH", "/projects/([\\w-]+)/assumptions/(\\w+)", () => fail(400, DEMO_RO));
R("POST", "/projects/([\\w-]+)/rebuild", () => fail(400, DEMO_RO));
R("POST", "/projects/([\\w-]+)/linkcheck", () => fail(400, "Bản demo không mở được mạng ngoài để kiểm link — tính năng chạy trên máy chủ thật."));
R("POST", "/projects/([\\w-]+)/shares", (b, [slug]) => {
  const u = need(), p = getProject(slug, u, true); if (!p.exported) fail(400, "Chưa có hồ sơ để chia sẻ — chạy Plan trước.");
  const tok = Math.random().toString(36).slice(2, 12) + Math.random().toString(36).slice(2, 12);
  const x = {id: nid(), project_id: p.id, token: tok, label: String(b.label || "").slice(0, 80), created: now(), views: 0, last_view: null, revoked: 0, url: "/s/" + tok};
  D.shares.push(x); audit(u.id, "share_create", slug); return x;
});
R("DELETE", "/shares/(\\d+)", (b, [id]) => { const u = need(), x = D.shares.find(x => x.id === +id) || fail(404, "Không có"); getProject(D.projects.find(p => p.id === x.project_id).slug, u, true); x.revoked = 1; return {ok: true}; });
R("PATCH", "/projects/([\\w-]+)", (b, [slug]) => { const p = getProject(slug, need(), true); for (const k of ["name", "idea", "country"]) if (b[k]) p[k] = String(b[k]).trim(); p.updated = now(); return summary(p); });
R("DELETE", "/projects/([\\w-]+)", (b, [slug]) => { const u = need(), p = getProject(slug, u, true); D.projects = D.projects.filter(x => x.id !== p.id); D.messages = D.messages.filter(m => m.project_id !== p.id); D.decisions = D.decisions.filter(d => d.project_id !== p.id); delete D.interview[p.id]; audit(u.id, "project_delete", slug); return {ok: true}; });
R("GET", "/projects/([\\w-]+)/messages", (b, [slug], q) => { const p = getProject(slug, need()); return D.messages.filter(m => m.project_id === p.id && m.room === q.get("room")); });
R("POST", "/projects/([\\w-]+)/interview", async (b, [slug]) => { const u = need(), p = getProject(slug, u, true); if (!String(b.text || "").trim()) fail(400, "Trống"); return interviewTurn(p, u, String(b.text).slice(0, 6000)); });
R("PUT", "/projects/([\\w-]+)/answers", (b, [slug]) => {
  const p = getProject(slug, need(), true), st = istate(p.id);
  for (const [k, v] of Object.entries(b)) if (QMAP[k]) { if (String(v).trim()) st.answers[k] = String(v).trim(); else delete st.answers[k]; }
  st.current_qid = nextUnanswered(st.answers); st.done = !st.current_qid; return {answers: st.answers, progress: progress(st.answers)};
});
R("POST", "/projects/([\\w-]+)/brainstorm", async (b, [slug]) => { const u = need(), p = getProject(slug, u, true); if (!String(b.text || "").trim()) fail(400, "Trống"); return brainstormTurn(p, u, String(b.text).slice(0, 6000)); });
R("POST", "/projects/([\\w-]+)/decisions", (b, [slug]) => {
  const p = getProject(slug, need(), true); if (!String(b.title || "").trim()) fail(400, "Cần tiêu đề");
  const d = {id: nid(), project_id: p.id, title: String(b.title).trim().slice(0, 200), detail: String(b.detail || ""), category: CATEGORIES.includes(b.category) ? b.category : "other",
    status: ["proposed", "locked"].includes(b.status) ? b.status : "locked", created: now(), updated: now()};
  D.decisions.push(d); return d;
});
const decOf = (u, id) => { const d = D.decisions.find(d => d.id === +id) || fail(404, "Không có"); getProject(D.projects.find(p => p.id === d.project_id).slug, u, true); return d; };
R("PATCH", "/decisions/(\\d+)", (b, [id]) => { const d = decOf(need(), id); for (const k of ["title", "detail"]) if (k in b) d[k] = String(b[k]); if (["proposed", "locked", "rejected"].includes(b.status)) d.status = b.status; if (CATEGORIES.includes(b.category)) d.category = b.category; d.updated = now(); return d; });
R("DELETE", "/decisions/(\\d+)", (b, [id]) => { decOf(need(), id); D.decisions = D.decisions.filter(d => d.id !== +id); return {ok: true}; });
R("POST", "/projects/([\\w-]+)/brief", (b, [slug]) => { const p = getProject(slug, need(), true); const md = buildBrief(p); if (["interview", "brainstorm"].includes(p.status)) p.status = "ready"; return {brief_md: md}; });
R("POST", "/projects/([\\w-]+)/run", (b, [slug]) => {
  const u = need(), p = getProject(slug, u, true);
  if (D.jobs.some(j => j.project_id === p.id && ["queued", "starting", "running"].includes(j.status))) fail(409, "Dự án đang có job chạy.");
  const miss = progress(istate(p.id).answers).required_missing;
  if (miss.length && !b.force) fail(400, "Còn câu phỏng vấn bắt buộc chưa trả lời: " + miss.join(", "));
  buildBrief(p);
  const mode = S("plan_billing"), j = {id: nid(), kind: "plan", project_id: p.id, user_id: u.id, status: "queued", log: "", attempt: 1, model: b.model || null, created: now(), usage: null, error: null};
  if (b.billing === "external") fail(400, "Agent ngoài cần máy chủ thật — agent của bạn gọi API của máy chủ bằng token.");
  if (b.billing === "demo") { if (S("allow_demo_engine") !== "1") fail(403, "Owner đã tắt engine demo"); Object.assign(j, {engine: "demo", billing: "demo"}); }
  else if (b.billing === "user_key") {
    if (mode === "owner") fail(403, "Hệ thống chỉ cho chạy Plan bằng tài khoản của owner.");
    const k = myKey(u, b.api_key_id), eng = PROVIDERS[k.provider].plan_engine;
    if (!eng) fail(400, `Key ${k.provider} chỉ dùng để chat. Chạy Plan cần key Anthropic (claude CLI) hoặc Gemini (agy).`);
    Object.assign(j, {engine: eng, billing: "user_key", api_key_id: k.id, key_hint: k.key_hint, model: b.model || k.model});
  } else {
    if (mode === "user_key") fail(403, "Hệ thống yêu cầu chạy Plan bằng API key của bạn.");
    const q = quota(u); if (q.owner_jobs_limit != null && q.owner_jobs_month >= q.owner_jobs_limit) fail(403, `Hết quota ${q.owner_jobs_limit} lần chạy/tháng bằng tài khoản hệ thống. Dùng API key của bạn hoặc liên hệ admin.`);
    const prof = activeProfile(); if (!prof) fail(503, "Hệ thống chưa có core agent sẵn sàng. Owner vào Admin → Core agent: tạo profile và đăng nhập.");
    Object.assign(j, {engine: prof.engine, billing: "owner", profile_id: prof.id});
  }
  D.jobs.push(j); p.status = "running"; p.updated = now(); audit(u.id, "job_create", slug, {job: j.id, billing: j.billing, engine: j.engine});
  setTimeout(() => simulate(j.id), 0); return {job_id: j.id};
});
const jobOf = (u, id) => { const j = D.jobs.find(j => j.id === +id); if (!j || (j.user_id !== u.id && !["owner", "admin"].includes(u.role))) fail(404, "Không có job"); return j; };
R("GET", "/jobs/(\\d+)", (b, [id]) => jobOf(need(), id));
R("POST", "/jobs/(\\d+)/cancel", (b, [id]) => { const u = need(), j = jobOf(u, id); if (["queued", "starting", "running"].includes(j.status)) { clearTimeout(timers[j.id]); j.status = "cancelled"; j.finished = now(); log(j, "— kết thúc: cancelled (Đã huỷ)"); const p = D.projects.find(p => p.id === j.project_id); if (p) p.status = "ready"; audit(u.id, "job_cancel", id); } return {ok: true}; });

// --- admin
const joinJob = j => { const p = D.projects.find(p => p.id === j.project_id), u = D.users.find(u => u.id === j.user_id), pr = D.profiles.find(x => x.id === j.profile_id);
  return {...j, slug: p?.slug, name: p?.name, email: u?.email, profile: pr?.name}; };
R("GET", "/admin/overview", () => {
  needAdmin(); const m = month(), mu = D.usage.filter(x => x.created >= m);
  const days = {}; for (const x of D.usage) { const d = x.created.slice(0, 10); days[d] ??= {d, i: 0, o: 0, n: 0}; days[d].i += x.input_tokens; days[d].o += x.output_tokens; days[d].n++; }
  return {users: D.users.length, users_active_30d: D.users.filter(u => u.last_login && Date.now() - new Date(u.last_login) < 30 * 864e5).length,
    projects: D.projects.length, projects_done: D.projects.filter(p => p.status === "done").length,
    jobs_running: D.jobs.filter(j => ["running", "starting"].includes(j.status)).length, jobs_queued: D.jobs.filter(j => j.status === "queued").length,
    jobs_month: D.jobs.filter(j => j.created >= m && j.kind === "plan").length, jobs_failed_month: D.jobs.filter(j => j.created >= m && j.status === "failed").length,
    tokens_month: mu.reduce((s, x) => s + x.input_tokens + x.output_tokens, 0), owner_tokens_month: mu.filter(x => x.profile_id).reduce((s, x) => s + x.input_tokens + x.output_tokens, 0),
    days: Object.values(days).sort((a, b) => a.d.localeCompare(b.d)).slice(-30), active_agent: activeProfile(),
    recent_jobs: [...D.jobs].reverse().slice(0, 8).map(joinJob),
    new_users_7d: D.users.filter(u => Date.now() - new Date(u.created) < 7 * 864e5).length, invites_open: D.invites.filter(i => !i.used_by && !i.revoked).length,
    funnel: (() => { const us = D.users.filter(u => u.role === "user"), f = {signup: us.length, key: 0, project: 0, plan: 0, share: 0};
      for (const u of us) { const ob = onboarding(u).steps; for (const [k, s] of [["key", "key"], ["project", "project"], ["plan", "plan"], ["share", "share"]]) f[k] += ob.find(x => x.id === s).done ? 1 : 0; } return f; })()};
});
R("GET", "/admin/users/(\\d+)", (b, [id]) => {
  needAdmin(); const t = D.users.find(u => u.id === +id) || fail(404, "Không có");
  const ps = D.projects.filter(p => p.user_id === t.id && !p.is_sample), us = D.usage.filter(x => x.user_id === t.id && x.created >= month());
  return {...pub(t), quota: quota(t), quota_projects: t.quota_projects, quota_jobs_month: t.quota_jobs_month, onboarding: onboarding(t),
    keys: D.keys.filter(k => k.user_id === t.id).map(k => ({provider: k.provider, model: k.model, key_hint: k.key_hint})),
    invited_by: D.users.find(u => u.id === t.invited_by)?.email || null, projects: ps.map(summary),
    jobs: D.jobs.filter(j => j.user_id === t.id).reverse().slice(0, 15).map(j => ({...j, name: D.projects.find(p => p.id === j.project_id)?.name})),
    usage: {i: us.reduce((s, x) => s + x.input_tokens, 0), o: us.reduce((s, x) => s + x.output_tokens, 0), n: us.length},
    activity: D.audit.filter(a => a.user_id === t.id).reverse().slice(0, 20)};
});
R("GET", "/admin/invites", () => (needAdmin(), [...D.invites].reverse().map(i => ({...i, used_email: D.users.find(u => u.id === i.used_by)?.email}))));
R("POST", "/admin/invites", (b) => {
  const a = needAdmin(), email = String(b.email || "").trim().toLowerCase() || null;
  if (email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) fail(400, "Email không hợp lệ");
  if (email && D.users.some(u => u.email === email)) fail(409, "Email này đã có tài khoản");
  const days = Math.max(1, Math.min(+b.days || 7, 90)), num = k => b[k] === "" || b[k] == null ? null : +b[k];
  const i = {id: nid(), token: Math.random().toString(36).slice(2) + Math.random().toString(36).slice(2), email, role: ["user", "admin"].includes(b.role) && (a.role === "owner" || b.role === "user") ? b.role : "user",
    quota_projects: num("quota_projects"), quota_jobs_month: num("quota_jobs_month"), note: String(b.note || "").slice(0, 200), created_by: a.id, created: now(),
    expires: new Date(Date.now() + days * 864e5).toISOString().replace(/\.\d+Z$/, "Z"), used_by: null, revoked: 0};
  D.invites.push(i); audit(a.id, "invite_create", email || "(link mở)"); return i;
});
R("DELETE", "/admin/invites/(\\d+)", (b, [id]) => { const a = needAdmin(), i = D.invites.find(i => i.id === +id); if (i) i.revoked = 1; audit(a.id, "invite_revoke", id); return {ok: true}; });
R("GET", "/admin/users", () => { needAdmin(); return D.users.map(u => ({...pub(u), quota: quota(u), quota_projects: u.quota_projects, quota_jobs_month: u.quota_jobs_month,
  onboarding: (o => ({done: o.done, total: o.total}))(onboarding(u)), keys: D.keys.filter(k => k.user_id === u.id).length, tokens_month: D.usage.filter(x => x.user_id === u.id && x.created >= month()).reduce((s, x) => s + x.input_tokens + x.output_tokens, 0), google: false})); });
R("POST", "/admin/users", (b) => {
  const a = needAdmin(), email = String(b.email || "").trim().toLowerCase();
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email) || String(b.password || "").length < 8) fail(400, "Email hoặc mật khẩu (≥ 8 ký tự) không hợp lệ");
  if (D.users.some(u => u.email === email)) fail(409, "Email đã tồn tại");
  const role = ["user", "admin"].includes(b.role) && (a.role === "owner" || b.role === "user") ? b.role : "user";
  const u = {id: nid(), email, name: b.name || email.split("@")[0], pw: hashish(b.password), role, status: "active", quota_projects: null, quota_jobs_month: null, created: now(), last_login: null};
  D.users.push(u); audit(a.id, "user_create", email, {role}); return pub(u);
});
R("PATCH", "/admin/users/(\\d+)", (b, [id]) => {
  const a = needAdmin(), t = D.users.find(u => u.id === +id) || fail(404, "Không có");
  if (t.role === "owner" && a.role !== "owner") fail(403, "Không sửa được owner");
  if ("role" in b) { if (a.role !== "owner" || !["user", "admin", "owner"].includes(b.role) || t.id === a.id) fail(403, "Chỉ owner đổi vai trò người khác"); t.role = b.role; }
  if (["active", "disabled"].includes(b.status)) { if (t.id === a.id) fail(400, "Không tự khoá chính mình"); t.status = b.status; }
  for (const k of ["quota_projects", "quota_jobs_month"]) if (k in b) t[k] = b[k] === "" || b[k] == null ? null : +b[k];
  if (b.password) { if (b.password.length < 8) fail(400, "Mật khẩu tối thiểu 8 ký tự"); t.pw = hashish(b.password); }
  audit(a.id, "user_update", t.email, Object.fromEntries(Object.entries(b).filter(([k]) => k !== "password"))); return {ok: true};
});
R("GET", "/admin/projects", () => { needAdmin(); return [...D.projects].sort((a, b) => b.updated.localeCompare(a.updated)).map(p => ({...summary(p), email: D.users.find(u => u.id === p.user_id)?.email})); });
R("GET", "/admin/jobs", (b, m, q) => { needAdmin(); const s = q.get("status"); return [...D.jobs].reverse().filter(j => !s || j.status === s).map(joinJob); });
R("POST", "/admin/jobs/(\\d+)/retry", (b, [id]) => {
  const a = needAdmin(), j = D.jobs.find(j => j.id === +id); if (!j || ["queued", "starting", "running"].includes(j.status) || j.kind !== "plan") fail(400, "Job không thể chạy lại");
  const prof = j.billing === "owner" ? activeProfile() : null; if (j.billing === "owner" && !prof) fail(503, "Chưa có core agent sẵn sàng");
  const n = {...j, id: nid(), status: "queued", log: "", error: null, created: now(), started: null, finished: null, engine: prof ? prof.engine : j.engine, profile_id: prof ? prof.id : j.profile_id};
  D.jobs.push(n); audit(a.id, "job_retry", id, {new: n.id}); setTimeout(() => simulate(n.id), 0); return {job_id: n.id};
});
R("GET", "/admin/usage", () => {
  needAdmin(); const m = month(), mu = D.usage.filter(x => x.created >= m), group = (f) => { const o = {}; for (const x of mu) { const k = f(x); o[k] ??= {k, i: 0, o: 0, n: 0, x}; o[k].i += x.input_tokens; o[k].o += x.output_tokens; o[k].n++; } return Object.values(o); };
  return {by_user: group(x => x.user_id + x.source).map(g => ({email: D.users.find(u => u.id === g.x.user_id)?.email, source: g.x.source, i: g.i, o: g.o, n: g.n})),
    by_profile: group(x => x.profile_id).filter(g => g.x.profile_id).map(g => ({name: D.profiles.find(p => p.id === g.x.profile_id)?.name, engine: "", i: g.i, o: g.o, c: null, n: g.n})),
    by_provider: group(x => x.provider + x.model).map(g => ({provider: g.x.provider, model: g.x.model, i: g.i, o: g.o, n: g.n}))};
});
R("GET", "/admin/audit", () => { needAdmin(); return [...D.audit].reverse().slice(0, 300).map(a => ({...a, email: D.users.find(u => u.id === a.user_id)?.email})); });

const profRow = p => ({...p, models: p.models || [], tokens_month: 0, jobs_month: D.jobs.filter(j => j.profile_id === p.id && j.created >= month()).length,
  installed: true, terminal: !!D.terminals[p.id]?.alive});
R("GET", "/admin/agents", () => { needOwner(); return {profiles: [...D.profiles].sort((a, b) => (b.is_active - a.is_active) || (a.priority - b.priority)).map(profRow),
  engines: Object.fromEntries(Object.entries(ENGINES).map(([k, e]) => [k, {...e, installed: true}]))}; });
const profOf = id => D.profiles.find(p => p.id === +id) || fail(404, "Không có profile");
R("POST", "/admin/agents", (b) => {
  const o = needOwner(); if (!ENGINES[b.engine] || !String(b.name || "").trim()) fail(400, "Cần tên và engine hợp lệ");
  const key = String(b.key || "").trim(), mode = b.auth_mode === "api_key" ? "api_key" : "account";
  const p = {id: nid(), name: b.name.trim(), engine: b.engine, auth_mode: mode, key_hint: key ? (key.length > 12 ? key.slice(0, 4) + "…" + key.slice(-4) : "…") : null,
    model: b.model || null, enabled: 1, is_active: D.profiles.length ? 0 : 1, priority: +b.priority || 100, account_label: b.account_label || null,
    status: b.engine === "demo" || (mode === "api_key" && key) ? "ready" : "needs_login", version: b.engine === "agy" ? "1.4.3" : b.engine === "claude" ? "2.1.305 (Claude Code)" : null,
    models: b.engine === "claude" ? ["sonnet", "opus", "haiku", "claude-sonnet-5-5", "claude-opus-5-5", "claude-haiku-5-5"] : [], quota_text: null, quota_checked: null, budget_tokens_month: null, created: now()};
  D.profiles.push(p); audit(o.id, "agent_add", p.name, {engine: p.engine, mode}); return profRow(p);
});
R("PATCH", "/admin/agents/(\\d+)", (b, [id]) => {
  const o = needOwner(), p = profOf(id);
  for (const k of ["name", "model", "account_label", "priority", "budget_tokens_month"]) if (k in b) p[k] = b[k];
  if ("enabled" in b) p.enabled = b.enabled ? 1 : 0; if (["account", "api_key"].includes(b.auth_mode)) p.auth_mode = b.auth_mode;
  if (b.key) { p.key_hint = b.key.length > 12 ? b.key.slice(0, 4) + "…" + b.key.slice(-4) : "…"; p.status = "ready"; }
  if (b.reset_status) p.status = "ready"; audit(o.id, "agent_update", p.name); return profRow(p);
});
R("POST", "/admin/agents/(\\d+)/activate", (b, [id]) => { const o = needOwner(), p = profOf(id); D.profiles.forEach(x => x.is_active = 0); p.is_active = 1; p.enabled = 1; audit(o.id, "agent_activate", p.name); return {ok: true}; });
R("DELETE", "/admin/agents/(\\d+)", (b, [id]) => { const o = needOwner(), p = profOf(id); D.profiles = D.profiles.filter(x => x.id !== p.id); delete D.terminals[p.id]; audit(o.id, "agent_delete", p.name); return {ok: true}; });
R("POST", "/admin/agents/(\\d+)/check", (b, [id]) => { needOwner(); const p = profOf(id); return {ok: true, output: (p.version || "demo") + " · (bản demo: kết quả ghi lại từ máy chủ thật)"}; });
R("POST", "/admin/agents/(\\d+)/models", (b, [id]) => {
  needOwner(); const p = profOf(id);
  if (p.engine === "agy" && p.status === "needs_login") return {models: [], output: "Fetching available models...\nError: Please sign in to view available models. Launch the CLI without arguments to sign in."};
  if (p.engine === "agy") return {models: [], output: "Bản demo không gọi được `agy models`. Trên máy chủ, danh sách model của tài khoản đã đăng nhập hiện ở đây."};
  return {models: p.models, output: "Claude Code nhận alias (sonnet/opus/haiku) hoặc model ID đầy đủ."};
});
R("POST", "/admin/agents/install", (b) => { const o = needOwner(); if (!["agy", "claude"].includes(b.engine)) fail(400, "Engine?"); const j = {id: nid(), kind: "install", engine: b.engine, user_id: o.id, status: "queued", log: "", attempt: 1, created: now()}; D.jobs.push(j); audit(o.id, "cli_install", b.engine); setTimeout(() => simulate(j.id), 0); return {job_id: j.id}; });
R("POST", "/admin/agents/(\\d+)/terminal", (b, [id]) => {
  const o = needOwner(), p = profOf(id), action = b.action || "login";
  let out = p.engine === "agy" ? AGY_MENU : "Welcome to Claude Code\n\nThis will guide you through long-lived (1-year) auth token setup for your Claude account.\n";
  if (action === "usage") out += "\n> /usage\n[Bản demo: trên máy chủ, màn hình quota của tài khoản hiện ở đây và được lưu lại khi đóng terminal.]\n";
  if (action === "logout") out += "\n> /logout\n✓ [mô phỏng] Đã đăng xuất.\n";
  D.terminals[p.id] = {action, out, alive: action !== "logout", step: 0};
  if (action === "logout") p.status = "needs_login";
  audit(o.id, "agent_terminal", id, {action}); return {ok: true};
});
R("GET", "/admin/agents/(\\d+)/terminal", (b, [id]) => { needOwner(); const t = D.terminals[+id]; return t ? {output: termText(t), urls: [], alive: t.alive, action: t.action} : {output: "", urls: [], alive: false, action: null}; });
R("POST", "/admin/agents/(\\d+)/terminal/input", (b, [id]) => { needOwner(); termInput(profOf(id), String(b.text || "")); return {ok: true}; });
R("POST", "/admin/agents/(\\d+)/terminal/stop", (b, [id]) => {
  needOwner(); const p = profOf(id), t = D.terminals[p.id];
  if (t?.loggedIn) p.status = "ready";
  if (t?.action === "usage") { p.quota_text = termText(t); p.quota_checked = now(); }
  delete D.terminals[p.id]; return {ok: true};
});
R("GET", "/admin/settings", () => { needOwner(); return {...D.settings, google_client_secret_set: false}; });
R("PUT", "/admin/settings", (b) => { const o = needOwner(); for (const k of Object.keys(DEFAULT_SETTINGS)) if (k in b) D.settings[k] = String(b[k]); audit(o.id, "settings_update", "", b); return {...D.settings, google_client_secret_set: false}; });
R("POST", "/admin/seed-sample", () => { const o = needOwner(); if (D.projects.some(p => p.slug === SAMPLE_SLUG)) fail(409, "Đã nạp mẫu rồi"); seedSample(o); audit(o.id, "seed_sample", SAMPLE_SLUG); return {slug: SAMPLE_SLUG}; });

// ------------------------------------------------------------------ fetch shim
const realFetch = window.fetch.bind(window);
window.fetch = async (input, init = {}) => {
  const url = typeof input === "string" ? input : input.url;
  if (!url.startsWith("/api/")) return realFetch(input, init);
  const u = new URL(url, "http://x"), path = u.pathname.slice(4), method = (init.method || "GET").toUpperCase();
  let body = {}; try { body = init.body ? JSON.parse(init.body) : {}; } catch {}
  for (const [m, re, fn] of routes) {
    const hit = m === method && path.match(re);
    if (!hit) continue;
    try { const out = await fn(body, hit.slice(1), u.searchParams); save(); return new Response(JSON.stringify(out ?? {}), {status: 200, headers: {"Content-Type": "application/json"}}); }
    catch (e) { save(); if (!(e instanceof HttpErr)) console.error(e); return new Response(JSON.stringify({detail: e.message}), {status: e.status || 500, headers: {"Content-Type": "application/json"}}); }
  }
  return new Response(JSON.stringify({detail: "Không có API " + method + " " + path}), {status: 404});
};

// ------------------------------------------------------------------ điều hướng & tải file
let downloads = null;
const getDownloads = () => downloads ??= (window.claude?.use ? window.claude.use("downloads").catch(() => null) : Promise.resolve(null));
async function saveFile(filename, data) {
  const dl = await getDownloads();
  if (!dl) { window.toast?.("Trình xem này không cho tải file."); return; }
  try { await dl.save({filename, data}); window.toast?.("Đã gửi " + filename); }
  catch (e) { window.toast?.(e.code === "declined" ? "Đã huỷ tải." : "Chưa tải được: " + (e.message || e.code)); }
}
async function saveProjectFile(slug, f) {
  if (slug !== SAMPLE_SLUG) { window.toast?.("Bản demo chỉ có file thật cho dự án mẫu. Dự án của bạn cần máy chủ thật để build Word/PowerPoint/Excel."); return; }
  const bin = !f.endsWith(".md");
  const r = await realFetch(`files/${f}${bin ? ".b64.txt" : ".txt"}`); if (!r.ok) { window.toast?.("Thiếu file " + f); return; }
  let data; if (bin) { const s = atob((await r.text()).trim()), b = new Uint8Array(s.length); for (let i = 0; i < s.length; i++) b[i] = s.charCodeAt(i); data = new Blob([b]); } else data = await r.text();
  saveFile(`${slug}-${f}`, data);
}
window.addEventListener("message", e => { const m = e.data; if (m && m.gp === "download") saveProjectFile(m.project, m.file); });
window.GPDEMO = {
  invite: null,
  openInvite(token) { D.session = null; save(); window.GPDEMO.invite = token; window.GPDEMO.nav("login"); },
  saveBrief(slug) { const p = D.projects.find(p => p.slug === slug); if (p) saveFile(`${slug}-brief.md`, p.brief_md || buildBrief(p)); },
  async reset() { if (!await ask("Xoá toàn bộ dữ liệu demo trên trình duyệt này?", "Xoá & làm lại")) return; try { localStorage.removeItem(KEY); } catch {} D = blank(); window.GPDEMO.nav("login"); },
  projectName(slug) { return D.projects.find(p => p.slug === slug)?.name || ""; },
  aiLive: async () => !!(await getSample()) && !aiOff,
};
})();
