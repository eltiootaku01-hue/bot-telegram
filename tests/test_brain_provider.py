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
