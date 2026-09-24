# -*- coding: utf-8 -*-
"""Clasificación centralizada de errores de providers."""

from __future__ import annotations

from .errors import (
    InputTooLargeError,
    MissingApiKeyError,
    ProviderError,
    ProviderProtocolError,
    ProviderRateLimitError,
    ProviderRemoteError,
    ProviderTimeoutError,
)

from .models import FailureClass


def classify_provider_error(
    error: ProviderError,
) -> FailureClass:

    if isinstance(
        error,
        ProviderRateLimitError,
    ):
        return FailureClass.QUOTA

    if isinstance(
        error,
        MissingApiKeyError,
    ):
        return FailureClass.AUTHENTICATION

    if isinstance(
        error,
        InputTooLargeError,
    ):
        return FailureClass.INPUT

    if isinstance(
        error,
        ProviderTimeoutError,
    ):
        return FailureClass.TEMPORARY

    if isinstance(
        error,
        ProviderProtocolError,
    ):
        return FailureClass.PROTOCOL

    if isinstance(
        error,
        ProviderRemoteError,
    ):
        return FailureClass.PROVIDER

    return FailureClass.UNKNOWN