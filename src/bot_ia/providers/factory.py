# -*- coding: utf-8 -*-
"""Construcción de providers desde la configuración de runtime."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Callable

from bot_ia.config import RuntimeConfig

from .adapters import (
    GroqProvider,
    HttpTransport,
    OllamaProvider,
    OpenAIProvider,
    OpenRouterProvider,
)
from .coze import CozeProvider
from .manager import ProviderManager

KeyLoader = Callable[[str], str | None]

_PROVIDER_TYPES = {
    "openai": OpenAIProvider,
    "groq": GroqProvider,
    "coze": CozeProvider,
    "openrouter": OpenRouterProvider,
    "ollama": OllamaProvider,
}


def build_provider_manager(
    config: RuntimeConfig,
    *,
    key_loader: KeyLoader | None = None,
    transports: Mapping[str, HttpTransport] | None = None,
) -> ProviderManager:
    transports = transports or {}
    providers = []

    for provider_config in config.providers:
        if not provider_config.enabled:
            continue

        provider_type = _PROVIDER_TYPES.get(provider_config.provider_id)
        if provider_type is None:
            raise ValueError(f"unsupported provider: {provider_config.provider_id}")

        accounts = tuple(sorted(provider_config.accounts, key=lambda a: a.priority))
        if not accounts:
            accounts = (None,)

        for account in accounts:
            if account is not None and not account.enabled:
                continue

            options: dict[str, object] = {
                "account_id": account.account_id if account else provider_config.provider_id,
                "enabled": True,
                "key_loader": key_loader,
                "transport": transports.get(provider_config.provider_id),
                "base_url": provider_config.base_url,
                "default_model": provider_config.model,
                "default_max_output_tokens": provider_config.max_output_tokens,
                "default_timeout_seconds": provider_config.timeout_seconds,
                "cooldown_seconds": account.cooldown_seconds if account else 60.0,
            }
            if account is not None:
                options["api_key_env"] = account.secret_env

            providers.append(provider_type(**options))

    return ProviderManager(
        tuple(providers),
        provider_configs={p.provider_id: p for p in config.providers},
    )
