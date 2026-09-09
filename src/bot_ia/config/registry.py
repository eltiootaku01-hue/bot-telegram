"""Registro central de providers y servicios configurados."""

from __future__ import annotations

from .models import ProviderConfig, RuntimeConfig, ServiceConfig


class RuntimeRegistry:
    def __init__(self, config: RuntimeConfig) -> None:
        self._config = config

    def provider(self, provider_id: str) -> ProviderConfig:
        config = self._config.provider(provider_id)
        if not config.enabled:
            raise ValueError(f"provider is disabled: {provider_id}")
        return config

    def service(self, service_id: str) -> ServiceConfig:
        config = self._config.service(service_id)
        if not config.enabled:
            raise ValueError(f"service is disabled: {service_id}")
        return config

    @property
    def config(self) -> RuntimeConfig:
        return self._config
