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
    assert BrainClient(settings).configured_providers() == ["groq", "gemini", "openrouter"]


def test_provider_order_without_preference_is_stable() -> None:
    settings = Settings(
        gemini_api_key="gemi-key",
        cerebras_api_key="c-key",
    )
    assert BrainClient(settings).configured_providers() == ["gemini", "cerebras"]


def test_personality_prompt_contains_identity() -> None:
    client = BrainClient(Settings(groq_api_key="key"))
    request = LLMRequest(identity=BotIdentity.SUNNA, user_text="hola")
    prompt = client._system_prompt(request)
    assert "Sunna" in prompt
    assert "kuudere" in prompt


def test_default_models_exist_for_all_supported_providers() -> None:
    assert set(DEFAULT_MODELS) == {"gemini", "groq", "cerebras", "openrouter"}


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
