"""LLM của user (BYOK). Mỗi user tự thêm API key; server chỉ giữ bản mã hoá và gọi thẳng API của nhà cung cấp.

Provider 'demo' chạy không cần key (trả lời theo kịch bản) để thử luồng sản phẩm offline.
"""
import json
import re
import time

import httpx

PROVIDERS = {
    "anthropic": {"label": "Anthropic (Claude)", "models": ["claude-sonnet-5-5", "claude-opus-5-5", "claude-haiku-5-5"],
                  "plan_engine": "claude"},
    "openai": {"label": "OpenAI", "models": [], "plan_engine": None},
    # Alias "-latest" do Google tự trỏ sang bản hiện hành — không bị ngừng như tên phiên bản cố định
    "gemini": {"label": "Google Gemini", "models": ["gemini-flash-latest", "gemini-pro-latest"], "plan_engine": "agy"},
    "openrouter": {"label": "OpenRouter", "models": [], "plan_engine": "claude"},   # Plan: Claude Code qua Anthropic Skin, chỉ model anthropic/*
}
TIMEOUT = httpx.Timeout(120, connect=15)


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
        if provider in ("openai", "openrouter"):
            url = "https://api.openai.com/v1/chat/completions" if provider == "openai" else "https://openrouter.ai/api/v1/chat/completions"
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
            msg = msg.get("error", msg)
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
