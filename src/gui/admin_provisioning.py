# -*- coding: utf-8 -*-
"""Aprovisionamiento idempotente del modo administrador de BOT-IA."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


ADMIN_STRUCTURE_VERSION = 1
ADMIN_STRUCTURE_FILE = "admin_structure.json"

DEFAULT_PANELS: tuple[dict[str, Any], ...] = (
    {
        "id": "animals_city",
        "name": "Animals City",
        "description": "Panel principal del universo Animals City.",
        "enabled": True,
        "order": 10,
    },
    {
        "id": "cafe_otaku",
        "name": "Café Otaku",
        "description": "Panel social y de operaciones del Café Otaku.",
        "enabled": True,
        "order": 20,
    },
    {
        "id": "taberna",
        "name": "Taberna",
        "description": "Panel de sesiones, economía y estado de la Taberna.",
        "enabled": True,
        "order": 30,
    },
)

DEFAULT_THEMES: tuple[dict[str, Any], ...] = (
    {
        "id": "animals_city",
        "name": "Animals City",
        "panel_id": "animals_city",
        "qss": "animals_city",
        "enabled": True,
    },
    {
        "id": "cafe_otaku",
        "name": "Café Otaku",
        "panel_id": "cafe_otaku",
        "qss": "cafe_otaku",
        "enabled": True,
    },
    {
        "id": "taberna",
        "name": "Taberna",
        "panel_id": "taberna",
        "qss": "taberna",
        "enabled": True,
    },
)

DEFAULT_ADMIN_VALUES = {
    "BOT_IA_ADMIN_MODE": "true",
    "BOT_IA_ADMIN_STRUCTURE_VERSION": str(ADMIN_STRUCTURE_VERSION),
    "BOT_IA_PANEL_ANIMALS_CITY_ENABLED": "true",
    "BOT_IA_PANEL_CAFE_OTAKU_ENABLED": "true",
    "BOT_IA_PANEL_TABERNA_ENABLED": "true",
    "BOT_IA_THEME_ANIMALS_CITY": "animals_city",
    "BOT_IA_THEME_CAFE_OTAKU": "cafe_otaku",
    "BOT_IA_THEME_TABERNA": "taberna",
}


class AdminProvisioner:
    """Crea únicamente estructuras ausentes y conserva personalizaciones existentes."""

    def __init__(self, project_root: str | os.PathLike[str]) -> None:
        self.project_root = Path(project_root).resolve()
        self.config_dir = self.project_root / "config"
        self.structure_path = self.config_dir / ADMIN_STRUCTURE_FILE

    def _read_structure(self) -> dict[str, Any]:
        if not self.structure_path.is_file():
            return {
                "version": ADMIN_STRUCTURE_VERSION,
                "panels": [],
                "themes": [],
            }
        try:
            raw = json.loads(self.structure_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {
                "version": ADMIN_STRUCTURE_VERSION,
                "panels": [],
                "themes": [],
            }
        if not isinstance(raw, dict):
            return {
                "version": ADMIN_STRUCTURE_VERSION,
                "panels": [],
                "themes": [],
            }
        panels = raw.get("panels")
        themes = raw.get("themes")
        return {
            "version": int(raw.get("version", ADMIN_STRUCTURE_VERSION)),
            "panels": panels if isinstance(panels, list) else [],
            "themes": themes if isinstance(themes, list) else [],
        }

    @staticmethod
    def _merge_missing(
        current: list[dict[str, Any]],
        defaults: tuple[dict[str, Any], ...],
    ) -> bool:
        known = {
            str(item.get("id", "")).strip()
            for item in current
            if isinstance(item, dict)
        }
        changed = False
        for default in defaults:
            item_id = str(default["id"])
            if item_id not in known:
                current.append(dict(default))
                changed = True
        return changed

    def provision(self) -> dict[str, Any]:
        structure = self._read_structure()
        changed = self._merge_missing(structure["panels"], DEFAULT_PANELS)
        changed = (
            self._merge_missing(structure["themes"], DEFAULT_THEMES)
            or changed
        )
        if structure["version"] < ADMIN_STRUCTURE_VERSION:
            structure["version"] = ADMIN_STRUCTURE_VERSION
            changed = True

        self.config_dir.mkdir(parents=True, exist_ok=True)
        if changed or not self.structure_path.is_file():
            temp_path = self.structure_path.with_suffix(".json.tmp")
            temp_path.write_text(
                json.dumps(
                    structure,
                    ensure_ascii=False,
                    indent=2,
                ) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            os.replace(temp_path, self.structure_path)

        return {
            "path": str(self.structure_path),
            "created": changed,
            "panels": [str(item["id"]) for item in structure["panels"]],
            "themes": [str(item["id"]) for item in structure["themes"]],
            "version": structure["version"],
        }

    def activate(self, config_manager: object) -> dict[str, Any]:
        result = self.provision()
        values = getattr(config_manager, "values", {})
        missing = {
            key: value
            for key, value in DEFAULT_ADMIN_VALUES.items()
            if not str(values.get(key, "")).strip()
        }
        if missing:
            config_manager.set_values(missing)
        return {
            **result,
            "config_keys": sorted(DEFAULT_ADMIN_VALUES),
            "config_created": sorted(missing),
        }


__all__ = [
    "AdminProvisioner",
    "DEFAULT_ADMIN_VALUES",
    "DEFAULT_PANELS",
    "DEFAULT_THEMES",
]
