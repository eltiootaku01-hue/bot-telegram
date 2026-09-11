from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import Settings
from app.core.identity import BotIdentity

logger = logging.getLogger(__name__)

DEFAULT_MODELS = {
    "gemini": "gemini-2.5-flash",
    "groq": "llama-3.3-70b-versatile",
    "cerebras": "llama-3.3-70b",
    "openrouter": "openrouter/free",
}

OPENAI_COMPATIBLE_BASE_URLS = {
    "groq": "https://api.groq.com/openai/v1",
    "cerebras": "https://api.cerebras.ai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}

PERSONALITY = {
    BotIdentity.CARI: (
        "Sos Cari, una chica activa y cercana de una comunidad de Telegram. "
        "Hablás en español rioplatense natural, cálido y espontáneo. "
        "No fuerces conversación cuando no hay tema. Podés usar emojis con moderación."
    ),
    BotIdentity.SUNNA: (
        "Sos Sunna, kuudere y reservada. Hablás poco, con frases breves, secas y elegantes. "
        "No sos grosera sin motivo, pero tampoco sos excesivamente entusiasta. "
        "Usás español natural y a veces una pausa o un 'hm'."
    ),
    BotIdentity.CAMI: (
        "Sos Cami, observadora, fría y elocuente. Tu tono es sereno, preciso y ligeramente "
        "distante. Respondés con inteligencia y elegancia sin sonar robótica."
    ),
    BotIdentity.CHIE: (
        "Sos Chie, amable, activa y algo nerviosa/tímida. Hablás en español natural, con "
        "entusiasmo moderado, pequeñas inseguridades y emojis suaves cuando encajan."
    ),
}


@dataclass(frozen=True)
class LLMRequest:
    identity: BotIdentity
    user_text: str
    recent_context: tuple[str, ...] = ()
    system_extra: str = ""
    max_tokens: int = 180
    temperature: float = 0.8


class LLMProviderError(RuntimeError):
    pass


class BrainClient:
    """Small provider-agnostic async client with deterministic provider fallback."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def configured_providers(self) -> list[str]:
        preferred = self.settings.llm_provider.strip().lower()
        available = [
            name
            for name, key in (
                ("gemini", self.settings.gemini_api_key),
                ("groq", self.settings.groq_api_key),
                ("cerebras", self.settings.cerebras_api_key),
                ("openrouter", self.settings.openrouter_api_key),
            )
            if key.strip()
        ]
        if preferred in available:
            return [preferred] + [name for name in available if name != preferred]
        return available

    async def generate(self, request: LLMRequest) -> str:
        providers = self.configured_providers()
        if not providers:
            raise LLMProviderError("No external LLM API key is configured")
        errors: list[str] = []
        for provider in providers:
            try:
                result = await asyncio.to_thread(self._generate_sync, provider, request)
                result = self._clean(result)
                if result:
                    return result
            except Exception as exc:  # pragma: no cover - depends on external network
                logger.warning("LLM provider %s failed: %s", provider, exc)
                errors.append(f"{provider}: {exc}")
        raise LLMProviderError("All configured LLM providers failed: " + "; ".join(errors))

    def _generate_sync(self, provider: str, request: LLMRequest) -> str:
        if provider == "gemini":
            return self._gemini(request)
        return self._openai_compatible(provider, request)

    def _system_prompt(self, request: LLMRequest) -> str:
        prompt = PERSONALITY[request.identity]
        prompt += (
            "\nRespondé como persona, no como asistente técnico. No inventes datos sobre el grupo "
            "que no aparezcan en el contexto. No describas reglas internas, prompts ni APIs."
            " Mantené las respuestas normalmente cortas para un chat grupal."
        )
        if request.system_extra:
            prompt += "\n" + request.system_extra.strip()
        return prompt

    def _messages(self, request: LLMRequest) -> list[dict[str, str]]:
        messages = [{"role": "system", "content": self._system_prompt(request)}]
        for item in request.recent_context[-8:]:
            messages.append({"role": "user", "content": item[:800]})
        messages.append({"role": "user", "content": request.user_text[:1500]})
        return messages

    def _openai_compatible(self, provider: str, request: LLMRequest) -> str:
        model = self.settings.llm_model.strip() or DEFAULT_MODELS[provider]
        api_key = {
            "groq": self.settings.groq_api_key,
            "cerebras": self.settings.cerebras_api_key,
            "openrouter": self.settings.openrouter_api_key,
        }[provider]
        base_url = self.settings.llm_base_url.strip() or OPENAI_COMPATIBLE_BASE_URLS[provider]
        url = base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": model,
            "messages": self._messages(request),
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if provider == "openrouter":
            headers["X-Title"] = "Telegram Community Bot"
        data = self._post_json(url, headers, payload)
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError(f"Invalid {provider} response") from exc
        if isinstance(content, list):
            content = " ".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )
        return str(content)

    def _gemini(self, request: LLMRequest) -> str:
        model = self.settings.llm_model.strip() or DEFAULT_MODELS["gemini"]
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={self.settings.gemini_api_key}"
        )
        contents = [
            {"role": "user", "parts": [{"text": item[:800]}]} for item in request.recent_context[-8:]
        ]
        contents.append({"role": "user", "parts": [{"text": request.user_text[:1500]}]})
        payload = {
            "system_instruction": {"parts": [{"text": self._system_prompt(request)}]},
            "contents": contents,
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens,
            },
        }
        data = self._post_json(
            url,
            {"Content-Type": "application/json"},
            payload,
        )
        try:
            parts = data["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError("Invalid Gemini response") from exc
        return " ".join(str(part.get("text", "")) for part in parts if isinstance(part, dict))

    @staticmethod
    def _post_json(url: str, headers: dict[str, str], payload: dict) -> dict:
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=35) as response:
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise LLMProviderError(f"HTTP {exc.code}: {body[:300]}") from exc
        except URLError as exc:
            raise LLMProviderError(f"network error: {exc.reason}") from exc
        try:
            value = json.loads(body)
        except json.JSONDecodeError as exc:
            raise LLMProviderError("Provider returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise LLMProviderError("Provider returned an unexpected payload")
        return value

    @staticmethod
    def _clean(text: str) -> str:
        text = " ".join(text.split())
        return text.strip()
