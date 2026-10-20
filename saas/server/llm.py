"""LLM của user (BYOK). Mỗi user tự thêm API key; server chỉ giữ bản mã hoá và gọi thẳng API của nhà cung cấp.

Provider 'demo' chạy không cần key (trả lời theo kịch bản) để thử luồng sản phẩm offline.
"""
import json
import re

import httpx

PROVIDERS = {
    "anthropic": {"label": "Anthropic (Claude)", "models": ["claude-sonnet-5-5", "claude-opus-5-5", "claude-haiku-5-5"],
                  "plan_engine": "claude"},
    "openai": {"label": "OpenAI", "models": [], "plan_engine": None},
    "gemini": {"label": "Google Gemini", "models": ["gemini-2.5-pro", "gemini-2.5-flash"], "plan_engine": "agy"},
    "openrouter": {"label": "OpenRouter", "models": [], "plan_engine": None},
}
TIMEOUT = httpx.Timeout(120, connect=15)


class LLMError(Exception):
    pass


def chat(provider: str, key: str, model: str, system: str, messages: list[dict], max_tokens=1800) -> tuple[str, dict]:
    """messages = [{role: user|assistant, content}] → (text, usage{input_tokens, output_tokens})."""
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
        raise LLMError(f"HTTP {r.status_code}: {msg}")
    return r.json()


def parse_json(text: str) -> dict:
    """Model được yêu cầu trả JSON; vẫn chịu được ```json fences hoặc chữ thừa quanh nó."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {"reply": text.strip()}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"reply": text.strip()}
