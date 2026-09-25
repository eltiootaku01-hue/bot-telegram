# -*- coding: utf-8 -*-
"""Persistencia dinámica de configuración local y hot-reload del runtime."""

from __future__ import annotations

import os
from pathlib import Path
import re
import tempfile
from typing import Mapping

from dotenv import dotenv_values, load_dotenv, set_key

_ENV_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class DynamicConfigManager:
    """Sincroniza .env, os.environ y la configuración activa del runtime."""

    def __init__(
        self,
        project_root: str | os.PathLike[str],
        runtime: object | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.env_path = self.project_root / ".env"
        self.example_path = self.project_root / ".env.example"
        self.runtime = runtime
        self.values: dict[str, str] = {}
        self.load()

    def load(self, *, override: bool = False) -> dict[str, str]:
        """Carga .env sin sobrescribir variables externas salvo override=True."""
        load_dotenv(self.env_path, override=override)
        raw = dotenv_values(self.env_path)
        self.values = {
            str(key): os.getenv(str(key), str(value or ""))
            for key, value in raw.items()
            if key
        }
        self._refresh_runtime()
        return dict(self.values)

    def get(self, key: str, default: str = "") -> str:
        return os.getenv(
            key,
            self.values.get(key, default),
        )

    def set_values(self, values: Mapping[str, object]) -> dict[str, str]:
        """Persiste valores mediante set_key y actualiza el proceso en caliente."""
        self.env_path.parent.mkdir(parents=True, exist_ok=True)
        updates: dict[str, str] = {}

        for key, raw_value in values.items():
            key = str(key).strip()
            if not _ENV_KEY.fullmatch(key):
                raise ValueError(f"invalid environment key: {key!r}")
            value = "" if raw_value is None else str(raw_value).strip()
            set_key(
                str(self.env_path),
                key,
                value,
                quote_mode="auto",
            )
            os.environ[key] = value
            updates[key] = value

        self.values.update(updates)
        self._refresh_runtime()
        return dict(self.values)

    def ensure_defaults(self, values: Mapping[str, object]) -> dict[str, str]:
        """Persiste sólo variables ausentes y conserva valores personalizados."""
        missing = {
            str(key): value
            for key, value in values.items()
            if not str(self.get(str(key), "")).strip()
        }
        if not missing:
            return dict(self.values)
        return self.set_values(missing)

    def reset_to_factory(self) -> dict[str, str]:
        """Reemplaza .env por .env.example y aplica esos valores inmediatamente."""
        if not self.example_path.is_file():
            raise FileNotFoundError(
                f"factory configuration not found: {self.example_path}"
            )

        old = dotenv_values(self.env_path)
        factory = dotenv_values(self.example_path)
        factory_text = self.example_path.read_text(
            encoding="utf-8",
        )

        self.env_path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=".env.",
            suffix=".tmp",
            dir=self.env_path.parent,
        )
        os.close(fd)
        temp_path = Path(temp_name)
        try:
            temp_path.write_text(
                factory_text,
                encoding="utf-8",
                newline="\n",
            )
            os.replace(temp_path, self.env_path)
        finally:
            if temp_path.exists():
                temp_path.unlink()

        for key, old_value in old.items():
            if not key:
                continue
            if key not in factory and old_value is not None:
                current = os.environ.get(key)
                if current == str(old_value):
                    os.environ.pop(key, None)

        load_dotenv(
            self.env_path,
            override=True,
        )
        self.values = {
            str(key): os.getenv(str(key), str(value or ""))
            for key, value in factory.items()
            if key
        }
        self._refresh_runtime()
        return dict(self.values)

    def _refresh_runtime(self) -> None:
        """Recarga el RuntimeConfig sin recrear el proceso GUI."""
        if self.runtime is None:
            return

        try:
            from bot_ia.config.loader import load_default_runtime_config

            config = load_default_runtime_config(
                self.project_root
            )
            object.__setattr__(
                self.runtime,
                "config",
                config,
            )
            registry = getattr(
                self.runtime,
                "registry",
                None,
            )
            if registry is not None:
                registry._config = config

            provider_manager = getattr(
                self.runtime,
                "provider_manager",
                None,
            )
            if provider_manager is not None:
                provider_manager._provider_configs = {
                    provider.provider_id: provider
                    for provider in config.providers
                }
        except Exception:
            # Secrets can be updated even while an unrelated runtime config
            # is temporarily invalid; the next application rebuild reports it.
            return


__all__ = ["DynamicConfigManager"]
