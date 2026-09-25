from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


BOT_IDENTITIES = ("cari", "sunna", "cami", "chie")


@dataclass(frozen=True, slots=True)
class BotSnapshot:
    identity: str
    state: str = "IDLE"
    thread_id: int | None = None
    zone: str = "cafe"
    x: float = 0.0
    y: float = 0.0
    local_latency_ms: float | None = None
    network_latency_ms: float | None = None
    status: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def label(self) -> str:
        return self.identity.title()


@dataclass(frozen=True, slots=True)
class StateSnapshot:
    bots: tuple[BotSnapshot, ...]
    fetched_at: str = ""
    service_latency_ms: float | None = None
    metrics: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: dict[str, Any], elapsed_ms: float) -> "StateSnapshot":
        raw_bots = payload.get("bots", payload.get("identities", []))
        if isinstance(raw_bots, dict):
            raw_bots = [
                {"identity": identity, **(value if isinstance(value, dict) else {})}
                for identity, value in raw_bots.items()
            ]
        result: list[BotSnapshot] = []
        for raw in raw_bots if isinstance(raw_bots, list) else []:
            if not isinstance(raw, dict):
                continue
            identity = str(raw.get("identity", raw.get("bot_identity", ""))).casefold()
            if identity not in BOT_IDENTITIES:
                continue
            thread = raw.get("message_thread_id", raw.get("thread_id"))
            try:
                thread_id = int(thread) if thread is not None else None
            except (TypeError, ValueError):
                thread_id = None
            result.append(
                BotSnapshot(
                    identity=identity,
                    state=str(raw.get("state", raw.get("fsm_state", raw.get("status", "IDLE")))),
                    thread_id=thread_id,
                    zone=str(raw.get("zone", raw.get("zone_key", "cafe"))),
                    x=float(raw.get("x", raw.get("position_x", 0))),
                    y=float(raw.get("y", raw.get("position_y", 0))),
                    local_latency_ms=_number(raw.get("local_latency_ms")),
                    network_latency_ms=_number(raw.get("network_latency_ms")),
                    status=str(raw.get("status", "")),
                    metrics=dict(raw.get("metrics", {})) if isinstance(raw.get("metrics"), dict) else {},
                )
            )
        return cls(
            bots=tuple(result),
            fetched_at=str(payload.get("timestamp", payload.get("updated_at", ""))),
            service_latency_ms=elapsed_ms,
            metrics=dict(payload.get("metrics", {})) if isinstance(payload.get("metrics"), dict) else {},
        )


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
