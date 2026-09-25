from __future__ import annotations
import hashlib, json
from pathlib import Path
from typing import Any

class LoreEngine:
    """JSON-driven dialogue/personality engine."""
    def __init__(self, lore_dir: str | Path | None = None) -> None:
        self.lore_dir = Path(lore_dir) if lore_dir else Path(__file__).resolve().parents[1] / "config" / "lores"
        self._lores: dict[str, dict[str, Any]] = {}
        self._load_all()

    def _load_all(self) -> None:
        for path in sorted(self.lore_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            identity = str(data.get("identity", "")).strip().lower()
            if not identity or identity in self._lores:
                raise ValueError(f"Invalid or duplicate lore identity: {path}")
            self._validate(data, path)
            self._lores[identity] = data

    @staticmethod
    def _validate(data: dict[str, Any], path: Path) -> None:
        events = data.get("events")
        if not isinstance(events, dict) or "default" not in events:
            raise ValueError(f"Invalid lore events in {path}")
        for name, spec in events.items():
            if not isinstance(spec, dict) or not isinstance(spec.get("templates"), list) or not spec["templates"] or not all(isinstance(x, str) for x in spec["templates"]):
                raise ValueError(f"Invalid templates for {name!r} in {path}")

    @property
    def identities(self) -> tuple[str, ...]:
        return tuple(sorted(self._lores))

    def format_response(self, identity: str, event_type: str, context: dict) -> str:
        key = identity.strip().lower()
        if key not in self._lores:
            raise KeyError(f"Unknown lore identity: {identity}")
        events = self._lores[key]["events"]
        templates = events.get(event_type, events["default"])["templates"]
        raw = json.dumps({"identity": key, "event_type": event_type, "context": context}, ensure_ascii=False, sort_keys=True, default=str)
        template = templates[int(hashlib.sha256(raw.encode()).hexdigest(), 16) % len(templates)]
        values = dict(context)
        values["context"] = self._render_context(context)
        return template.format_map(_SafeFormat(values))

    @staticmethod
    def _render_context(context: dict) -> str:
        return ", ".join(f"{k}={v}" for k, v in context.items()) if context else "sin datos adicionales"

class _SafeFormat(dict[str, Any]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"
