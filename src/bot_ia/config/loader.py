"""Carga de configuración de runtime sin secretos ni red."""

from __future__ import annotations

from pathlib import Path
import tomllib

from .models import (
    ProviderAccountConfig,
    ProviderConfig,
    RuntimeConfig,
    ServiceConfig,
    UniverseConfig,
)


def _parse_account(
    provider_id: str,
    account_id: str,
    raw: object,
) -> ProviderAccountConfig:
    if not isinstance(raw, dict):
        raise ValueError(
            f"account configuration is invalid: "
            f"{provider_id}.{account_id}"
        )

    return ProviderAccountConfig(
        account_id=account_id,
        secret_env=str(raw.get("secret_env", "")),
        enabled=bool(raw.get("enabled", True)),
        priority=int(raw.get("priority", 100)),
        cooldown_seconds=float(
            raw.get("cooldown_seconds", 60.0)
        ),
    )


def _parse_provider(
    provider_id: str,
    raw: object,
) -> ProviderConfig:
    if not isinstance(raw, dict):
        raise ValueError(
            f"provider configuration is invalid: "
            f"{provider_id}"
        )

    fallback = raw.get("fallback")

    if fallback == "":
        fallback = None

    accounts_raw = raw.get("accounts", {})

    if not isinstance(accounts_raw, dict):
        raise ValueError(
            f"accounts configuration is invalid: "
            f"{provider_id}"
        )

    accounts = tuple(
        _parse_account(
            provider_id,
            account_id,
            account_raw,
        )
        for account_id, account_raw
        in accounts_raw.items()
    )

    return ProviderConfig(
        provider_id=provider_id,
        model=str(raw.get("model", "")),
        fallback_provider=fallback,
        max_output_tokens=int(
            raw.get("max_output_tokens", 128)
        ),
        timeout_seconds=float(
            raw.get("timeout_seconds", 30.0)
        ),
        enabled=bool(
            raw.get("enabled", True)
        ),
        base_url=str(raw.get("base_url", "")),
        accounts=accounts,
    )


def _parse_service(
    service_id: str,
    raw: object,
) -> ServiceConfig:
    if not isinstance(raw, dict):
        raise ValueError(
            f"service configuration is invalid: "
            f"{service_id}"
        )

    return ServiceConfig(
        service_id=service_id,
        enabled=bool(
            raw.get("enabled", False)
        ),
        url=str(
            raw.get("url", "")
        ),
    )


def _parse_universe(
    universe_id: str,
    raw: object,
) -> UniverseConfig:
    if not isinstance(raw, dict):
        raise ValueError(
            f"universe configuration is invalid: "
            f"{universe_id}"
        )

    return UniverseConfig(
        universe_id=universe_id,
        display_name=str(
            raw.get("display_name", "")
        ),
        root_path=Path(
            str(raw.get("root_path", ""))
        ).expanduser(),
        spoiler_policy=str(
            raw.get("spoiler_policy", "strict")
        ),
        language=str(
            raw.get("language", "es")
        ),
    )


def load_runtime_config(
    path: Path,
) -> RuntimeConfig:
    if not path.is_file():
        raise FileNotFoundError(
            f"configuration file not found: {path}"
        )

    with path.open("rb") as handle:
        data = tomllib.load(handle)

    providers_raw = data.get(
        "providers",
        {},
    )

    services_raw = data.get(
        "services",
        {},
    )

    universes_raw = data.get(
        "universes",
        {},
    )

    if not isinstance(
        providers_raw,
        dict,
    ):
        raise ValueError(
            "providers configuration is invalid"
        )

    if not isinstance(
        services_raw,
        dict,
    ):
        raise ValueError(
            "services configuration is invalid"
        )

    if not isinstance(
        universes_raw,
        dict,
    ):
        raise ValueError(
            "universes configuration is invalid"
        )

    providers = tuple(
        _parse_provider(
            provider_id,
            raw,
        )
        for provider_id, raw
        in providers_raw.items()
    )

    services = tuple(
        _parse_service(
            service_id,
            raw,
        )
        for service_id, raw
        in services_raw.items()
    )

    universes = tuple(
        _parse_universe(
            universe_id,
            raw,
        )
        for universe_id, raw
        in universes_raw.items()
    )

    if not providers:
        raise ValueError(
            "at least one provider is required"
        )

    return RuntimeConfig(
        providers,
        services,
        universes,
    )


def load_default_runtime_config(
    project_root: Path,
) -> RuntimeConfig:
    return load_runtime_config(
        project_root
        / "config"
        / "runtime.toml"
    )


def load_provider_config(
    path: Path,
) -> ProviderConfig:
    """Compatibilidad con la configuración antigua."""

    if not path.is_file():
        raise FileNotFoundError(
            f"configuration file not found: {path}"
        )

    with path.open("rb") as handle:
        data = tomllib.load(handle)

    provider = data.get("provider")

    if isinstance(provider, dict):
        return _parse_provider(
            str(provider.get("id", "")),
            provider,
        )

    runtime = load_runtime_config(path)

    return runtime.providers[0]


def load_default_provider_config(
    project_root: Path,
) -> ProviderConfig:
    return load_provider_config(
        project_root
        / "config"
        / "runtime.toml"
    )