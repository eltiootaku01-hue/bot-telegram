from app.brain.provider import BrainClient, DEFAULT_MODELS, LLMRequest
from app.core.config import Settings
from app.core.identity import BotIdentity


def test_provider_order_prefers_configured_provider() -> None:
    settings = Settings(
        llm_provider="groq",
        groq_api_key="g-key",
        gemini_api_key="gemi-key",
        openrouter_api_key="router-key",
    )
    assert BrainClient(settings).configured_providers() == ["groq", "gemini", "openrouter", "ollama"]


def test_provider_order_without_preference_is_stable() -> None:
    settings = Settings(
        gemini_api_key="gemi-key",
        cerebras_api_key="c-key",
    )
    assert BrainClient(settings).configured_providers() == ["gemini", "cerebras", "ollama"]


def test_ollama_can_be_the_only_backend() -> None:
    settings = Settings(ollama_model="llama3.2:1b", ollama_base_url="http://127.0.0.1:11434")
    assert BrainClient(settings).configured_providers() == ["ollama"]


def test_personality_prompt_contains_identity() -> None:
    client = BrainClient(Settings(groq_api_key="key"))
    request = LLMRequest(identity=BotIdentity.SUNNA, user_text="hola")
    prompt = client._system_prompt(request)
    assert "Sunna" in prompt
    assert "kuudere" in prompt


def test_default_models_exist_for_all_supported_providers() -> None:
    assert set(DEFAULT_MODELS) == {"gemini", "groq", "cerebras", "openrouter", "ollama"}


def test_gemini_keeps_api_key_out_of_url() -> None:
    settings = Settings(llm_provider="gemini", gemini_api_key="secret-key")
    client = BrainClient(settings)
    captured: dict[str, object] = {}

    def fake_post_json(url: str, headers: dict[str, str], payload: dict) -> dict:
        captured.update(url=url, headers=headers, payload=payload)
        return {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}

    client._post_json = fake_post_json  # type: ignore[method-assign]
    result = client._gemini(LLMRequest(identity=BotIdentity.CARI, user_text="hola"))

    assert result == "ok"
    assert captured["url"] == (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.5-flash:generateContent"
    )
    assert "secret-key" not in str(captured["url"])
    assert captured["headers"]["x-goog-api-key"] == "secret-key"  # type: ignore[index]


def test_ollama_request_uses_local_api_without_auth_header() -> None:
    settings = Settings(llm_provider="ollama", ollama_model="llama3.2:1b")
    client = BrainClient(settings)
    captured: dict[str, object] = {}

    def fake_post_json(url: str, headers: dict[str, str], payload: dict) -> dict:
        captured.update(url=url, headers=headers, payload=payload)
        return {"message": {"content": "ok"}}

    client._post_json = fake_post_json  # type: ignore[method-assign]
    result = client._ollama(LLMRequest(identity=BotIdentity.CARI, user_text="hola"))

    assert result == "ok"
    assert captured["url"] == "http://127.0.0.1:11434/api/chat"
    assert captured["headers"] == {"Content-Type": "application/json"}
    assert captured["payload"]["model"] == "llama3.2:1b"  # type: ignore[index]
