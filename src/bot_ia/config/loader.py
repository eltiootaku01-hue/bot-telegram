"""Carga de configuración de runtime sin secretos ni red."""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
import re
import tomllib

from .models import ProviderAccountConfig, ProviderConfig, RuntimeConfig, ServiceConfig, UniverseConfig

_UNRESOLVED_ENV = re.compile(r"(?:\$\{?[A-Za-z_][A-Za-z0-9_]*\}?|%[A-Za-z_][A-Za-z0-9_]*%)")


def _parse_account(provider_id: str, account_id: str, raw: object) -> ProviderAccountConfig:
    if not isinstance(raw, dict):
        raise ValueError(f"account configuration is invalid: {provider_id}.{account_id}")
    return ProviderAccountConfig(account_id=account_id, secret_env=str(raw.get("secret_env", "")), enabled=bool(raw.get("enabled", True)), priority=int(raw.get("priority", 100)), cooldown_seconds=float(raw.get("cooldown_seconds", 60.0)))


def _parse_provider(provider_id: str, raw: object) -> ProviderConfig:
    if not isinstance(raw, dict):
        raise ValueError(f"provider configuration is invalid: {provider_id}")
    fallback = raw.get("fallback")
    if fallback == "":
        fallback = None
    accounts_raw = raw.get("accounts", {})
    if not isinstance(accounts_raw, dict):
        raise ValueError(f"accounts configuration is invalid: {provider_id}")
    accounts = tuple(_parse_account(provider_id, account_id, account_raw) for account_id, account_raw in accounts_raw.items())
    return ProviderConfig(provider_id=provider_id, model=str(raw.get("model", "")), fallback_provider=fallback, max_output_tokens=int(raw.get("max_output_tokens", 128)), timeout_seconds=float(raw.get("timeout_seconds", 30.0)), enabled=bool(raw.get("enabled", True)), base_url=str(raw.get("base_url", "")), accounts=accounts)


def _parse_service(service_id: str, raw: object) -> ServiceConfig:
    if not isinstance(raw, dict):
        raise ValueError(f"service configuration is invalid: {service_id}")
    return ServiceConfig(service_id=service_id, enabled=bool(raw.get("enabled", False)), url=str(raw.get("url", "")))


def _resolve_universe_path(raw_path: object, *, config_dir: Path) -> Path:
    raw = str(raw_path).strip()
    if not raw:
        raise ValueError("universe root_path is required")
    if raw.startswith("env:"):
        env_name = raw[4:].strip()
        if not env_name:
            raise ValueError("universe root_path env reference is empty")
        value = os.environ.get(env_name)
        if not value or not value.strip():
            return config_dir / ".unconfigured" / env_name
        raw = value.strip()
    else:
        expanded = os.path.expandvars(raw)
        if _UNRESOLVED_ENV.search(expanded):
            raise ValueError(f"universe root_path contains an unresolved environment variable: {raw}")
        raw = expanded
    path = Path(raw).expanduser()
    return path.resolve() if path.is_absolute() else (config_dir / path).resolve()


def _parse_universe(universe_id: str, raw: object, *, config_dir: Path) -> UniverseConfig:
    if not isinstance(raw, dict):
        raise ValueError(f"universe configuration is invalid: {universe_id}")
    return UniverseConfig(
        universe_id=universe_id,
        display_name=str(raw.get("display_name", "")),
        root_path=_resolve_universe_path(raw.get("root_path", ""), config_dir=config_dir),
        spoiler_policy=str(raw.get("spoiler_policy", "strict")),
        language=str(raw.get("language", "es")),
        reference_universe_id=(str(raw["reference_universe_id"]) if raw.get("reference_universe_id") else None),
        reference_display_name=(str(raw["reference_display_name"]) if raw.get("reference_display_name") else None),
    )


def _activate_explicit_local_ollama(providers: tuple[ProviderConfig, ...]) -> tuple[ProviderConfig, ...]:
    """Keep Ollama off by default; enable it only after explicit launcher selection."""
    if os.getenv("BOT_IA_PROVIDER", "").strip().lower() != "ollama":
        return providers
    if os.getenv("BOT_IA_ENABLE_LOCAL_OLLAMA", "").strip().lower() not in {"1", "true", "yes", "on"}:
        return providers
    return tuple(
        replace(provider, enabled=True) if provider.provider_id == "ollama" else provider
        for provider in providers
    )


def load_runtime_config(path: Path) -> RuntimeConfig:
    if not path.is_file():
        raise FileNotFoundError(f"configuration file not found: {path}")
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    providers_raw = data.get("providers", {})
    services_raw = data.get("services", {})
    universes_raw = data.get("universes", {})
    if not isinstance(providers_raw, dict) or not isinstance(services_raw, dict) or not isinstance(universes_raw, dict):
        raise ValueError("runtime configuration sections are invalid")
    providers = tuple(_parse_provider(provider_id, raw) for provider_id, raw in providers_raw.items())
    providers = _activate_explicit_local_ollama(providers)
    services = tuple(_parse_service(service_id, raw) for service_id, raw in services_raw.items())
    universes = tuple(_parse_universe(universe_id, raw, config_dir=path.parent) for universe_id, raw in universes_raw.items())
    if not providers:
        raise ValueError("at least one provider is required")
    return RuntimeConfig(providers, services, universes)


def load_default_runtime_config(project_root: Path) -> RuntimeConfig:
    return load_runtime_config(project_root / "config" / "runtime.toml")


def load_provider_config(path: Path) -> ProviderConfig:
    """Compatibilidad con la configuración antigua."""
    if not path.is_file():
        raise FileNotFoundError(f"configuration file not found: {path}")
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    provider = data.get("provider")
    if isinstance(provider, dict):
        return _parse_provider(str(provider.get("id", "")), provider)
    return load_runtime_config(path).providers[0]


def load_default_provider_config(project_root: Path) -> ProviderConfig:
    return load_provider_config(project_root / "config" / "runtime.toml")
