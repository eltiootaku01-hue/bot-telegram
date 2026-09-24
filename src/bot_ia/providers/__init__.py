# -*- coding: utf-8 -*-
"""Gateway de proveedores de BOT-IA."""

from .adapters import (
    BaseProvider,
    GroqProvider,
    OpenAICompatibleProvider,
    OpenAIProvider,
    OpenRouterProvider,
    OllamaProvider,
)
from .coze import CozeProvider
from .factory import build_provider_manager

from .health import ProviderHealthRecord

from .manager import (
    ProviderManager,
    ProviderOutcome,
)

from .models import (
    FailureClass,
    ProviderAccount,
    ProviderHealth,
    ProviderModel,
    ProviderRequest,
    ProviderResponse,
    ProviderStatus,
    ProviderUsage,
)

__all__ = [
    "BaseProvider",
    "CozeProvider",
    "GroqProvider",
    "OpenAICompatibleProvider",
    "OpenAIProvider",
    "OpenRouterProvider",
    "OllamaProvider",
    "build_provider_manager",
    "ProviderHealthRecord",
    "ProviderManager",
    "ProviderOutcome",
    "FailureClass",
    "ProviderAccount",
    "ProviderHealth",
    "ProviderModel",
    "ProviderRequest",
    "ProviderResponse",
    "ProviderStatus",
    "ProviderUsage",
]
