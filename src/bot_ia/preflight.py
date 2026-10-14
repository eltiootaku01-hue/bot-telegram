# -*- coding: utf-8 -*-
"""Offline, read-only diagnostics for BOT-IA runtime configuration."""

from __future__ import annotations

import json
import os
from pathlib import Path
import time
from typing import Any

from bot_ia.config.loader import load_runtime_config
from bot_ia.librarian.inventory import SourceInventory

_EXIT_READY = 0
_EXIT_BLOCKED = 2
_EXIT_INVALID = 3
_PROVIDER_IDS = ("openai", "groq", "openrouter", "coze", "ollama")
_UNIVERSE_ENV = {
    "one_neko_punch": "BOT_IA_ONE_NEKO_PUNCH_ROOT",
    "neko_fish_online": "BOT_IA_NEKO_FISH_ONLINE_ROOT",
    "neko_of_the_dead": "BOT_IA_NEKO_OF_THE_DEAD_ROOT",
    "my_neko_academia": "BOT_IA_MY_NEKO_ACADEMIA_ROOT",
    "attack_on_neko": "BOT_IA_ATTACK_ON_NEKO_ROOT",
}
_MAX_SCAN_SECONDS = 0.5
_MAX_SCAN_DIRECTORIES = 500
_MAX_SCAN_FILES = 5000
_MAX_SCAN_BYTES = 20 * 1024 * 1024
_MAX_SOURCE_BYTES = 1024 * 1024


def _provider_chain(config: Any, provider_id: str) -> list[Any]:
    chain = []
    seen = set()
    current = provider_id
    while current and current not in seen:
        seen.add(current)
        try:
            provider = config.provider(current)
        except KeyError:
            break
        chain.append(provider)
        current = provider.fallback_provider
    return chain


def _inventory_is_bounded(root: Path) -> tuple[bool, str]:
    """Bound directory enumeration before invoking SourceInventory."""
    started = time.monotonic()
    directories = 0
    files = 0
    total_bytes = 0
    try:
        for current, names, filenames in os.walk(root, topdown=True, followlinks=False):
            directories += 1
            files += len(filenames)
            if directories > _MAX_SCAN_DIRECTORIES or files > _MAX_SCAN_FILES:
                return False, "LIMIT_EXCEEDED"
            if time.monotonic() - started > _MAX_SCAN_SECONDS:
                return False, "TIMEOUT"
            current_path = Path(current)
            names[:] = [name for name in names if not (current_path / name).is_symlink()]
            for filename in filenames:
                path = current_path / filename
                if path.suffix.casefold() not in {".md", ".txt", ".docx"}:
                    continue
                try:
                    size = path.stat().st_size
                except OSError:
                    return False, "UNREADABLE"
                if size > _MAX_SOURCE_BYTES:
                    return False, "LIMIT_EXCEEDED"
                total_bytes += size
                if total_bytes > _MAX_SCAN_BYTES:
                    return False, "LIMIT_EXCEEDED"
            if time.monotonic() - started > _MAX_SCAN_SECONDS:
                return False, "TIMEOUT"
    except OSError:
        return False, "UNREADABLE"
    return True, "BOUNDED"


def _universe_report(config: Any) -> list[dict[str, Any]]:
    configured = {universe.universe_id: universe for universe in config.universes}
    reports = []
    for universe_id, env_name in _UNIVERSE_ENV.items():
        universe = configured.get(universe_id)
        if universe is None:
            reports.append({
                "id": universe_id,
                "name": None,
                "root_env": env_name,
                "root_configured": False,
                "directory_accessible": False,
                "inventory_status": "UNKNOWN",
                "inventory_entries": None,
            })
            continue
        root = universe.root_path
        env_value = os.getenv(env_name, "").strip()
        root_configured = bool(env_value) if str(root).endswith(env_name) else True
        item: dict[str, Any] = {
            "id": universe_id,
            "name": universe.display_name,
            "root_env": env_name,
            "root_configured": root_configured,
            "directory_accessible": False,
            "inventory_status": "UNKNOWN",
            "inventory_entries": None,
        }
        try:
            item["directory_accessible"] = root_configured and root.is_dir() and os.access(root, os.R_OK)
        except OSError:
            item["directory_accessible"] = False
        if not item["directory_accessible"]:
            item["inventory_status"] = "NOT_ACCESSIBLE"
            reports.append(item)
            continue
        bounded, reason = _inventory_is_bounded(root)
        if not bounded:
            item["inventory_status"] = reason
            reports.append(item)
            continue
        try:
            entries = SourceInventory(root, max_file_bytes=_MAX_SOURCE_BYTES).discover(universe_id)
        except Exception as error:
            # Do not serialize exception messages: paths or input data may be sensitive.
            item["inventory_status"] = "ERROR"
            item["inventory_error_type"] = type(error).__name__
        else:
            item["inventory_status"] = "OK"
            item["inventory_entries"] = len(entries)
        reports.append(item)
    return reports


def build_report(project_root: Path) -> tuple[dict[str, Any], int]:
    """Build a stable report without constructing the application/runtime."""
    config_path = project_root / "config" / "runtime.toml"
    telegram_token_present = bool(os.getenv("TELEGRAM_BOT_TOKEN", "").strip())
    report: dict[str, Any] = {
        "schema_version": 1,
        "mode": "preflight",
        "configuration": {
            "path": "config/runtime.toml",
            "exists": config_path.is_file(),
            "status": "UNKNOWN",
            "error_type": None,
        },
        "telegram": {
            "token_variable": "TELEGRAM_BOT_TOKEN",
            "token_present": telegram_token_present,
            "status": "PRESENT" if telegram_token_present else "ABSENT",
            "authentication": "NOT_CHECKED",
        },
        "providers": [],
        "universes": [],
        "overall_status": "UNKNOWN",
        "exit_code": _EXIT_INVALID,
        "limitations": [
            "Credential presence is not authentication or connectivity.",
            "No network calls, runtime construction, database access, or services are started.",
        ],
    }
    if not config_path.is_file():
        report["configuration"]["status"] = "INVALID"
        report["configuration"]["error_type"] = "FileNotFoundError"
        report["overall_status"] = "BLOCKED"
        report["diagnostics"] = ["runtime configuration file is missing"]
        return report, _EXIT_INVALID
    try:
        config = load_runtime_config(config_path)
    except Exception as error:
        report["configuration"]["status"] = "INVALID"
        report["configuration"]["error_type"] = type(error).__name__
        report["overall_status"] = "BLOCKED"
        report["diagnostics"] = ["runtime configuration could not be loaded"]
        return report, _EXIT_INVALID

    report["configuration"]["status"] = "VALID"
    configured = {provider.provider_id: provider for provider in config.providers}
    for provider_id in _PROVIDER_IDS:
        provider = configured.get(provider_id)
        if provider is None:
            report["providers"].append({
                "id": provider_id,
                "configured": False,
                "enabled": False,
                "accounts": [],
                "status": "NOT_CONFIGURED",
            })
            continue
        accounts = []
        any_present = False
        for account in provider.accounts:
            present = bool(os.getenv(account.secret_env, "").strip())
            if account.enabled and present:
                any_present = True
            accounts.append({
                "account_id": account.account_id,
                "enabled": account.enabled,
                "secret_env": account.secret_env,
                "credential_present": present,
            })
        if provider.provider_id == "ollama":
            provider_status = "LOCAL_NO_KEY_REQUIRED" if provider.enabled else "DISABLED"
        elif not provider.enabled:
            provider_status = "DISABLED"
        elif any_present:
            provider_status = "CREDENTIAL_PRESENT"
        else:
            provider_status = "MISSING_CREDENTIAL"
        report["providers"].append({
            "id": provider_id,
            "configured": True,
            "enabled": provider.enabled,
            "accounts": accounts,
            "fallback": provider.fallback_provider,
            "status": provider_status,
        })

    selected_provider = os.getenv("BOT_IA_PROVIDER", "openai").strip() or "openai"
    selected_chain = _provider_chain(config, selected_provider)
    usable_chain = any(
        provider.enabled and (
            provider.provider_id == "ollama"
            or any(account.enabled and bool(os.getenv(account.secret_env, "").strip()) for account in provider.accounts)
        )
        for provider in selected_chain
    )
    report["selected_provider"] = selected_provider
    report["selected_provider_chain_has_configured_credential"] = usable_chain
    report["universes"] = _universe_report(config)
    missing_universe = any(item["inventory_status"] != "OK" for item in report["universes"])
    if not usable_chain:
        report["overall_status"] = "BLOCKED"
        report["diagnostics"] = ["selected provider and configured fallback chain have no usable configured credentials"]
        code = _EXIT_BLOCKED
    elif missing_universe or not telegram_token_present:
        report["overall_status"] = "WARNING"
        report["diagnostics"] = ["some optional local resources or credentials are absent or not inspectable"]
        code = _EXIT_READY
    else:
        report["overall_status"] = "READY"
        report["diagnostics"] = []
        code = _EXIT_READY
    report["exit_code"] = code
    return report, code


def run_preflight(project_root: Path) -> int:
    report, exit_code = build_report(project_root)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return exit_code
