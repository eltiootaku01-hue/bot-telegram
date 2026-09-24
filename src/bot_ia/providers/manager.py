# -*- coding: utf-8 -*-
"""Gateway central de ejecución, salud y fallback."""

from __future__ import annotations

from dataclasses import dataclass

from bot_ia.core.models import RouteDecision

from .adapters import BaseProvider
from .errors import ProviderError, ProviderDisabledError, ProviderRemoteError
from .health import ProviderHealthRecord
from .health_classifier import classify_provider_error
from .models import FailureClass, ProviderRequest, ProviderResponse, ProviderStatus, ProviderUsage


@dataclass(frozen=True, slots=True)
class ProviderOutcome:
    response: ProviderResponse
    attempts: tuple[str, ...]


class ProviderManager:
    """Selecciona cuentas por prioridad y aplica una cadena de fallback segura."""

    def __init__(self, providers: tuple[BaseProvider, ...], provider_configs: dict | None = None) -> None:
        self._providers: dict[str, BaseProvider] = {}
        self._account_providers: dict[tuple[str, str], BaseProvider] = {}
        self._health: dict[tuple[str, str], ProviderHealthRecord] = {}
        self._provider_configs = provider_configs or {}
        for provider in providers:
            self._providers.setdefault(provider.provider_id, provider)
            account_id = getattr(provider, "account_id", provider.provider_id)
            self._account_providers[(provider.provider_id, account_id)] = provider
            self._health[(provider.provider_id, account_id)] = ProviderHealthRecord(provider.provider_id, account_id)

    def execute(self, decision: RouteDecision, request: ProviderRequest, *, fallback_provider: str | None = None, fallback_accounts: tuple[str, ...] = ()) -> ProviderOutcome:
        if not (decision.requires_llm or decision.requires_search):
            return ProviderOutcome(ProviderResponse(provider="none", model=request.model, status=ProviderStatus.SKIPPED, output_text=None, usage=ProviderUsage(), latency_ms=0, request_id=request.request_id), ())

        attempts: list[str] = []
        candidates = self._candidate_pairs(request, fallback_provider, fallback_accounts)
        last_error: ProviderError | None = None
        for provider_id, account_id in candidates:
            provider = self._resolve(provider_id, account_id)
            if provider is None:
                error = ProviderDisabledError("provider account is not configured")
                last_error = error
                candidate = self._make_request(request, provider_id, account_id, None)
                attempts.append(self._attempt_name(provider_id, account_id))
                self._record_failure(candidate, error, None)
                continue
            if not getattr(provider, "enabled", True) or not self._available(provider_id, account_id):
                continue
            candidate = self._make_request(
                request,
                provider_id,
                account_id,
                provider,
            )
            try:
                response = self._call(candidate, attempts, provider)
                return ProviderOutcome(response, tuple(attempts))
            except ProviderError as error:
                last_error = error
                self._record_failure(candidate, error, provider)
                if not self._should_fallback(error):
                    break

        if last_error is None:
            return ProviderOutcome(self._error(request, "No provider account available", FailureClass.CONFIGURATION), tuple(attempts))
        return ProviderOutcome(self._error(request, type(last_error).__name__, classify_provider_error(last_error)), tuple(attempts))

    @staticmethod
    def _should_fallback(error: ProviderError) -> bool:
        """Sólo fallas recuperables justifican consumir otra cuenta/provider."""
        return classify_provider_error(error) in {
            FailureClass.QUOTA,
            FailureClass.AUTHENTICATION,
            FailureClass.TEMPORARY,
            FailureClass.PROVIDER,
        }

    def _candidate_pairs(self, request: ProviderRequest, fallback_provider: str | None, fallback_accounts: tuple[str, ...]) -> list[tuple[str, str | None]]:
        result: list[tuple[str, str | None]] = []
        visited: set[str] = set()
        def add_provider(provider_id: str, preferred_account: str | None = None) -> None:
            if not provider_id or provider_id in visited:
                return
            visited.add(provider_id)
            if preferred_account is not None:
                result.append((provider_id, preferred_account))
            else:
                provider_accounts = [key[1] for key in self._account_providers if key[0] == provider_id]
                result.extend((provider_id, account) for account in provider_accounts)
                if not provider_accounts:
                    result.append((provider_id, None))
            config = self._provider_configs.get(provider_id)
            next_fallback = getattr(config, "fallback_provider", None) if config is not None else None
            if next_fallback:
                add_provider(next_fallback)
        add_provider(request.provider, request.account_id)
        for account in fallback_accounts:
            if account and (request.provider, account) not in result:
                result.append((request.provider, account))
        if fallback_provider:
            add_provider(fallback_provider)
        return list(dict.fromkeys(result))

    def _resolve(self, provider_id: str, account_id: str | None) -> BaseProvider | None:
        if account_id is not None:
            return self._account_providers.get((provider_id, account_id))
        return self._providers.get(provider_id)

    def _make_request(
        self,
        request: ProviderRequest,
        provider_id: str,
        account_id: str | None,
        provider: BaseProvider | None,
        *,
    ) -> ProviderRequest:
        config = self._provider_configs.get(provider_id)
        model = getattr(provider, "default_model", None) if provider else None
        max_tokens = getattr(provider, "default_max_output_tokens", None) if provider else None
        timeout = getattr(provider, "default_timeout_seconds", None) if provider else None
        if config is not None:
            model, max_tokens, timeout = config.model, config.max_output_tokens, config.timeout_seconds
        timeout_value = timeout or request.timeout_seconds
        return ProviderRequest(
            provider_id,
            model or request.model,
            request.input_text,
            max_tokens or request.max_output_tokens,
            timeout_value,
            request.request_id,
            request.escalation_reason,
            account_id,
        )

    def _attempt_name(self, provider_id: str, account_id: str | None) -> str:
        return provider_id if account_id in (None, provider_id) else f"{provider_id}:{account_id}"

    def _available(self, provider_id: str, account_id: str | None) -> bool:
        record = self._health.get((provider_id, account_id or provider_id))
        return record is None or record.available

    def _call(self, request: ProviderRequest, attempts: list[str], provider: BaseProvider) -> ProviderResponse:
        attempts.append(self._attempt_name(request.provider, request.account_id))
        try:
            response = provider.generate(request)
        except ProviderError:
            raise
        except Exception as error:
            raise ProviderRemoteError("provider adapter failed unexpectedly") from error
        self._record_success(request, response)
        if len(attempts) > 1:
            return ProviderResponse(provider=response.provider, model=response.model, status=response.status, output_text=response.output_text, usage=response.usage, latency_ms=response.latency_ms, request_id=response.request_id, account_id=response.account_id, fallback_used=True, fallback_from=attempts[0])
        return response

    def _record_success(self, request: ProviderRequest, response: ProviderResponse) -> None:
        record = self._health.get((request.provider, request.account_id or request.provider))
        if record:
            record.register_success(response.usage.input_tokens, response.usage.output_tokens, response.usage.total_tokens)

    def _record_failure(self, request: ProviderRequest, error: ProviderError, provider: BaseProvider | None) -> None:
        record = self._health.get((request.provider, request.account_id or request.provider))
        if record:
            cooldown = getattr(provider, "cooldown_seconds", 0.0) if provider else 0.0
            record.register_failure(type(error).__name__, classify_provider_error(error), cooldown)

    @staticmethod
    def _error(request: ProviderRequest, error_type: str, failure_class: FailureClass) -> ProviderResponse:
        return ProviderResponse(provider=request.provider, model=request.model, status=ProviderStatus.ERROR, output_text=None, usage=ProviderUsage(), latency_ms=0, request_id=request.request_id, error_type=error_type, failure_class=failure_class)
