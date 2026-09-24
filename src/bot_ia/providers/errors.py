# -*- coding: utf-8 -*-
"""Errores tipados que nunca incluyen claves ni cuerpos de respuesta."""

class ProviderError(RuntimeError):
    pass


class ProviderDisabledError(ProviderError):
    pass


class MissingApiKeyError(ProviderError):
    pass


class ProviderTimeoutError(ProviderError):
    pass


class ProviderBudgetExceededError(ProviderError):
    """The total request budget is exhausted before another attempt."""

    pass


class ProviderRateLimitError(ProviderError):
    pass


class InputTooLargeError(ProviderError):
    pass


class ProviderRemoteError(ProviderError):
    pass


class ProviderProtocolError(ProviderError):
    pass
