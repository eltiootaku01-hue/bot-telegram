"""Configuración tipada del runtime."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ProviderAccountConfig:
    """Una credencial/cuenta independiente de un provider."""

    account_id: str
    secret_env: str
    enabled: bool = True
    priority: int = 100
    cooldown_seconds: float = 60.0

    def __post_init__(self) -> None:
        if not self.account_id:
            raise ValueError("account_id is required")

        if not self.secret_env:
            raise ValueError("secret_env is required")

        if self.priority < 0:
            raise ValueError("priority must be non-negative")

        if self.cooldown_seconds < 0:
            raise ValueError("cooldown_seconds must be non-negative")


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    """Configuración lógica de un provider."""

    provider_id: str
    model: str
    fallback_provider: str | None = None
    max_output_tokens: int = 128
    timeout_seconds: float = 30.0
    enabled: bool = True
    base_url: str = ""

    # Varias cuentas/API keys del mismo provider.
    accounts: tuple[ProviderAccountConfig, ...] = ()

    def __post_init__(self) -> None:
        if not self.provider_id:
            raise ValueError("provider_id is required")

        if not self.model:
            raise ValueError("model is required")

        if self.fallback_provider == self.provider_id:
            raise ValueError(
                "fallback_provider must differ from provider_id"
            )

        if self.max_output_tokens < 1:
            raise ValueError(
                "max_output_tokens must be positive"
            )

        if self.timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be positive"
            )

        account_ids = [
            account.account_id
            for account in self.accounts
        ]

        if len(account_ids) != len(set(account_ids)):
            raise ValueError(
                "provider account_id values must be unique"
            )


@dataclass(frozen=True, slots=True)
class ServiceConfig:
    service_id: str
    enabled: bool = False
    url: str = ""

    def __post_init__(self) -> None:
        if not self.service_id:
            raise ValueError("service_id is required")


@dataclass(frozen=True, slots=True)
class UniverseConfig:
    universe_id: str
    display_name: str
    root_path: Path
    spoiler_policy: str = "strict"
    language: str = "es"

    def __post_init__(self) -> None:
        if not self.universe_id:
            raise ValueError("universe_id is required")

        if not self.display_name:
            raise ValueError("display_name is required")

        if not self.root_path:
            raise ValueError("root_path is required")

        if not self.language:
            raise ValueError("language is required")


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    providers: tuple[ProviderConfig, ...]
    services: tuple[ServiceConfig, ...]
    universes: tuple[UniverseConfig, ...] = ()

    def provider(self, provider_id: str) -> ProviderConfig:
        for provider in self.providers:
            if provider.provider_id == provider_id:
                return provider

        raise KeyError(
            f"provider not configured: {provider_id}"
        )

    def service(self, service_id: str) -> ServiceConfig:
        for service in self.services:
            if service.service_id == service_id:
                return service

        raise KeyError(
            f"service not configured: {service_id}"
        )

    def universe(self, universe_id: str) -> UniverseConfig:
        for universe in self.universes:
            if universe.universe_id == universe_id:
                return universe

        raise KeyError(
            f"universe not configured: {universe_id}"
        )