"""LLM của user (BYOK). Mỗi user tự thêm API key; server chỉ giữ bản mã hoá và gọi thẳng API của nhà cung cấp.

Provider 'demo' chạy không cần key (trả lời theo kịch bản) để thử luồng sản phẩm offline.
"""
import json
import re
import time

import httpx

# plan_engine "native": Chạy Plan bằng chính key này qua engine native (gọi thẳng API, function calling) — CLI agy / Claude Code
# chỉ dùng cho tài khoản gói tháng của owner.
PROVIDERS = {
    "deepseek": {"label": "DeepSeek", "models": ["deepseek-flash", "deepseek-v4-pro"], "plan_engine": "native"},
    "anthropic": {"label": "Anthropic (Claude)", "models": ["claude-sonnet-5-5", "claude-opus-5-5", "claude-haiku-5-5"], "plan_engine": "native"},
    "openai": {"label": "OpenAI", "models": [], "plan_engine": "native"},
    # Alias "-latest" do Google tự trỏ sang bản hiện hành — không bị ngừng như tên phiên bản cố định
    "gemini": {"label": "Google Gemini", "models": ["gemini-flash-latest", "gemini-pro-latest"], "plan_engine": "native"},
    "openrouter": {"label": "OpenRouter", "models": [], "plan_engine": "native"},
}
# Điểm cuối chuẩn OpenAI (chat/completions + tools) của từng nhà cung cấp — engine native dùng một định dạng duy nhất.
OPENAI_COMPAT = {
    "deepseek": "https://api.deepseek.com/chat/completions",
    "openai": "https://api.openai.com/v1/chat/completions",
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
    "anthropic": "https://api.anthropic.com/v1/chat/completions",
}
# Giá USD / 1 triệu token: (vào, vào trúng cache, ra). Dùng giá giờ cao điểm cho chắc; model lạ → không biết giá, chặn theo token.
PRICES = {
    ("deepseek", "deepseek-flash"): (0.30, 0.006, 1.20), ("deepseek", "deepseek-chat"): (0.30, 0.006, 1.20),
    ("deepseek", "deepseek-v4-pro"): (1.32, 0.044, 3.96), ("deepseek", "deepseek-reasoner"): (1.32, 0.044, 3.96),
}
TIMEOUT = httpx.Timeout(120, connect=15)


def plan_model(provider):
    """Model mặc định khi Chạy Plan: model đầu danh sách (rẻ, gọi công cụ tốt). OpenAI/OpenRouter: người dùng phải chọn."""
    return next(iter((PROVIDERS.get(provider) or {}).get("models") or []), None)


class LLMError(Exception):
    def __init__(self, msg, suggested=None, status=None):
        super().__init__(msg)
        self.status = status
        self.suggested = suggested                     # model nhà cung cấp gợi ý thay thế (khi model cũ bị ngừng)


TRANSIENT = {408, 425, 429, 500, 502, 503, 504, 529}


def chat(provider: str, key: str, model: str, system: str, messages: list[dict], max_tokens=1800, retries=3) -> tuple[str, dict]:
    """messages = [{role: user|assistant, content}] → (text, usage). Lỗi tạm thời (quá tải, rate limit) tự thử lại có giãn cách."""
    for attempt in range(retries):
        try:
            return _chat(provider, key, model, system, messages, max_tokens)
        except LLMError as e:
            if e.status not in TRANSIENT or attempt == retries - 1:
                if e.status in TRANSIENT:
                    raise LLMError(f"Nhà cung cấp AI đang quá tải hoặc giới hạn lượt gọi (HTTP {e.status}) — đã thử {retries} lần, "
                                   "vui lòng gửi lại sau ít phút.", status=e.status) from e
                raise
            time.sleep(1.5 * (attempt + 1) ** 2)


def _chat(provider, key, model, system, messages, max_tokens):
    try:
        if provider == "anthropic":
            r = httpx.post("https://api.anthropic.com/v1/messages", timeout=TIMEOUT,
                           headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                           json={"model": model, "max_tokens": max_tokens, "system": system, "messages": messages})
            j = _ok(r)
            text = "".join(b.get("text", "") for b in j.get("content", []) if b.get("type") == "text")
            u = j.get("usage", {})
            return text, {"input_tokens": u.get("input_tokens", 0), "output_tokens": u.get("output_tokens", 0)}
        if provider in ("openai", "openrouter", "deepseek"):
            url = OPENAI_COMPAT[provider]
            r = httpx.post(url, timeout=TIMEOUT, headers={"Authorization": f"Bearer {key}"},
                           json={"model": model, "max_tokens": max_tokens,
                                 "messages": [{"role": "system", "content": system}, *messages]})
            j = _ok(r)
            u = j.get("usage", {})
            return j["choices"][0]["message"]["content"] or "", {"input_tokens": u.get("prompt_tokens", 0),
                                                                 "output_tokens": u.get("completion_tokens", 0)}
        if provider == "gemini":
            r = httpx.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                           timeout=TIMEOUT, headers={"x-goog-api-key": key},
                           json={"systemInstruction": {"parts": [{"text": system}]},
                                 "contents": [{"role": "model" if m["role"] == "assistant" else "user",
                                               "parts": [{"text": m["content"]}]} for m in messages],
                                 "generationConfig": {"maxOutputTokens": max_tokens}})
            j = _ok(r)
            parts = (j.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
            u = j.get("usageMetadata", {})
            return "".join(p.get("text", "") for p in parts), {"input_tokens": u.get("promptTokenCount", 0),
                                                               "output_tokens": u.get("candidatesTokenCount", 0)}
    except httpx.TimeoutException as e:
        raise LLMError(f"{provider} trả lời quá chậm", status=504) from e
    except httpx.HTTPError as e:
        raise LLMError(f"Không gọi được {provider}: {e}") from e
    raise LLMError(f"Provider chưa hỗ trợ: {provider}")


def _ok(r: httpx.Response) -> dict:
    if r.status_code >= 400:
        try:
            msg = r.json()
            msg = msg[0] if isinstance(msg, list) and msg else msg        # endpoint chuẩn OpenAI của Gemini trả lỗi dạng [{error}]
            msg = msg.get("error", msg) if isinstance(msg, dict) else msg
            msg = msg.get("message", msg) if isinstance(msg, dict) else msg
        except ValueError:
            msg = r.text[:300]
        m = re.search(r"use (?:models/)?((?:gemini|claude|gpt)[\w.-]*\w)", str(msg))
        raise LLMError(f"HTTP {r.status_code}: {msg}", suggested=m.group(1) if m and r.status_code in (400, 404) else None,
                       status=r.status_code)
    return r.json()


SKIP = re.compile(r"tts|image|embed|audio|live|transcribe|computer-use|robotics|banana|whisper|dall-e|moderation|realtime|search|vision-preview", re.I)


def list_models(provider: str, key: str) -> list[str]:
    """Model chat mà CHÍNH key này dùng được, hỏi thẳng nhà cung cấp."""
    try:
        if provider == "gemini":
            j = _ok(httpx.get("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200", headers={"x-goog-api-key": key}, timeout=30))
            ids = [m["name"].split("/", 1)[1] for m in j.get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]
        elif provider == "anthropic":
            j = _ok(httpx.get("https://api.anthropic.com/v1/models?limit=100", headers={"x-api-key": key, "anthropic-version": "2023-06-01"}, timeout=30))
            ids = [m["id"] for m in j.get("data", [])]
        elif provider == "openai":
            j = _ok(httpx.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {key}"}, timeout=30))
            ids = [m["id"] for m in j.get("data", []) if re.match(r"(gpt|o\d|chatgpt)", m["id"])]
        elif provider == "openrouter":
            j = _ok(httpx.get("https://openrouter.ai/api/v1/models", headers={"Authorization": f"Bearer {key}"}, timeout=30))
            ids = [m["id"] for m in j.get("data", [])]
        elif provider == "deepseek":
            j = _ok(httpx.get("https://api.deepseek.com/models", headers={"Authorization": f"Bearer {key}"}, timeout=30))
            ids = [m["id"] for m in j.get("data", [])]
        else:
            return []
    except httpx.HTTPError as e:
        raise LLMError(f"Không lấy được danh sách model: {e}") from e
    ids = [i for i in ids if not SKIP.search(i)]
    latest = [i for i in ids if i.endswith("-latest")]
    return latest + sorted((i for i in ids if i not in latest), reverse=True)


def parse_json(text: str) -> dict:
    """Model được yêu cầu trả JSON; vẫn chịu được ```json fences hoặc chữ thừa quanh nó."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {"reply": text.strip()}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"reply": text.strip()}


def chat_tools(provider, key, model, messages, tools, max_tokens=4096, retries=4):
    """Một lượt function calling chuẩn OpenAI → (message, usage). usage = {input, cached, output, cost_usd|None}.
    Dùng cho engine native: cùng một định dạng cho DeepSeek, OpenAI, Gemini, Anthropic, OpenRouter."""
    url = OPENAI_COMPAT.get(provider)
    if not url:
        raise LLMError(f"{provider} chưa hỗ trợ chạy Plan")
    payload = {"model": model, "messages": messages, "tools": tools, "tool_choice": "auto", "max_tokens": max_tokens}
    if provider == "openrouter":
        payload["usage"] = {"include": True}                  # OpenRouter trả chi phí thật của lượt gọi
    for attempt in range(retries):
        try:
            r = httpx.post(url, timeout=httpx.Timeout(300, connect=20), headers={"Authorization": f"Bearer {key}"}, json=payload)
            j = _ok(r)
            break
        except httpx.HTTPError as e:
            err = LLMError(f"Không gọi được {provider}: {type(e).__name__}", status=503)
        except LLMError as e:
            err = e
        if err.status not in TRANSIENT or attempt == retries - 1 or "PerDay" in str(err):   # hết lượt/ngày: thử lại vô ích
            raise err
        time.sleep(2 * (attempt + 1) ** 2)
    msg = (j.get("choices") or [{}])[0].get("message") or {}
    u = j.get("usage") or {}
    cached = u.get("prompt_cache_hit_tokens") or (u.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
    inp, out = u.get("prompt_tokens", 0), u.get("completion_tokens", 0)
    cost = u.get("cost") if provider == "openrouter" else None
    if cost is None:
        price = next((v for (p, m), v in PRICES.items() if p == provider and model.startswith(m)), None)
        if price:
            cost = ((inp - cached) * price[0] + cached * price[1] + out * price[2]) / 1e6
    return msg, {"input_tokens": inp, "cached_tokens": cached, "output_tokens": out, "cost_usd": cost}
