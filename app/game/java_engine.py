from __future__ import annotations

import atexit
import json
import os
import subprocess
import sys
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.game.models import CombatAction, CombatResult, Rarity


@dataclass(frozen=True, slots=True)
class EngineClientConfig:
    jar_path: Path
    java_command: str


class WaifuMonJavaEngine:
    """Persistent bridge to the authoritative Java WaifuMon rules engine."""

    CONTRACT_VERSION = "1.0"

    def __init__(self, *, config: EngineClientConfig | None = None) -> None:
        self._config = config or self._discover_config()
        self._process: subprocess.Popen[str] | None = None
        self._lock = threading.RLock()
        self._closed = False
        atexit.register(self.close)

    @staticmethod
    def _discover_config() -> EngineClientConfig:
        configured_jar = os.environ.get("WAIFUMON_JAVA_JAR", "").strip()
        configured_java = os.environ.get("WAIFUMON_JAVA_COMMAND", "").strip()
        roots = [
            Path(sys.executable).resolve().parent,
            Path(__file__).resolve().parents[2],
            Path.cwd().resolve(),
        ]

        candidates: list[Path] = []
        if configured_jar:
            candidates.append(Path(configured_jar))
        for root in roots:
            candidates.extend(
                [
                    root / "engine" / "waifumon" / "target" / "waifumon-engine.jar",
                    root / "engine" / "waifumon-engine.jar",
                    root / "engine" / "waifumon" / "waifumon-engine.jar",
                    root / ".." / "engine" / "waifumon" / "target" / "waifumon-engine.jar",
                    root / ".." / ".." / "engine" / "waifumon" / "target" / "waifumon-engine.jar",
                ]
            )

        jar_path = next((path.resolve() for path in candidates if path.exists()), None)
        if jar_path is None:
            raise RuntimeError(
                "WaifuMon Java engine JAR not found. Build engine/waifumon with Maven "
                "or set WAIFUMON_JAVA_JAR."
            )

        if configured_java:
            java_command = configured_java
        else:
            binary = "java.exe" if os.name == "nt" else "java"
            runtime_candidates: list[Path] = []
            for root in roots:
                runtime_candidates.extend(
                    [
                        root / "engine" / "jre" / "bin" / binary,
                        root / "engine" / "runtime" / "bin" / binary,
                        root / ".." / "engine" / "jre" / "bin" / binary,
                        root / ".." / ".." / "engine" / "jre" / "bin" / binary,
                    ]
                )
            bundled = next((path.resolve() for path in runtime_candidates if path.exists()), None)
            java_command = str(bundled) if bundled is not None else "java"

        return EngineClientConfig(jar_path=jar_path, java_command=java_command)

    def _start(self) -> None:
        if self._closed:
            raise RuntimeError("WaifuMon Java engine is closed")
        if self._process is not None and self._process.poll() is None:
            return
        self._process = subprocess.Popen(
            [self._config.java_command, "-jar", str(self._config.jar_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )

    def _call(
        self,
        *,
        player_id: int,
        community_id: int,
        command: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        request_id = uuid.uuid4().hex
        request = {
            "contract_version": self.CONTRACT_VERSION,
            "request_id": request_id,
            "correlation_id": request_id,
            "player_id": player_id,
            "community_id": community_id,
            "command": command,
            "payload": payload,
            "idempotency_key": idempotency_key,
        }

        with self._lock:
            self._start()
            assert self._process is not None
            assert self._process.stdin is not None
            assert self._process.stdout is not None
            self._process.stdin.write(
                json.dumps(request, ensure_ascii=False, separators=(",", ":")) + "\n"
            )
            self._process.stdin.flush()
            line = self._process.stdout.readline()
            if not line:
                return_code = self._process.poll()
                stderr = ""
                if self._process.stderr is not None:
                    stderr = self._process.stderr.read(4000)
                self._process = None
                raise RuntimeError(
                    f"WaifuMon Java engine stopped unexpectedly "
                    f"(returncode={return_code}): {stderr.strip()}"
                )

            response = json.loads(line)
            if response.get("request_id") not in {request_id, "unknown"}:
                raise RuntimeError("WaifuMon engine returned an unrelated request id")
            if not response.get("success", False):
                code = response.get("error_code") or response.get("errorCode") or "ENGINE_ERROR"
                message = response.get("error_message") or response.get("errorMessage") or "Java engine request failed"
                raise ValueError(f"{code}: {message}")
            return response

    def resolve_gacha(
        self,
        *,
        seed: str,
        d_streak: int,
        candidates: list[dict[str, str]],
        owned_character_ids: set[str] | frozenset[str],
        player_id: int,
        community_id: int,
    ) -> dict[str, Any]:
        response = self._call(
            player_id=player_id,
            community_id=community_id,
            command="gacha.resolve",
            payload={
                "seed": seed,
                "d_streak": d_streak,
                "candidates": candidates,
                "owned_character_ids": sorted(owned_character_ids),
            },
            idempotency_key=f"gacha:{community_id}:{player_id}:{seed}",
        )
        return dict(response["payload"])

    def roll_gacha(self, *, seed: str) -> Rarity:
        response = self._call(
            player_id=0,
            community_id=0,
            command="gacha.roll",
            payload={"seed": seed},
            idempotency_key=seed,
        )
        return Rarity(response["payload"]["rarity"])

    async def combat_async(
        self,
        *,
        attacker: dict[str, Any],
        defender: dict[str, Any],
        action: str,
        turn_id: str,
        player_id: int = 0,
        community_id: int = 0,
        idempotency_key: str | None = None,
    ) -> CombatResult:
        """Run the blocking Java bridge off the asyncio event loop."""
        import asyncio

        return await asyncio.to_thread(
            self.combat,
            attacker=attacker,
            defender=defender,
            action=action,
            turn_id=turn_id,
            player_id=player_id,
            community_id=community_id,
            idempotency_key=idempotency_key,
        )

    def combat(
        self,
        *,
        attacker: dict[str, Any],
        defender: dict[str, Any],
        action: str,
        turn_id: str,
        player_id: int = 0,
        community_id: int = 0,
        idempotency_key: str | None = None,
    ) -> CombatResult:
        response = self._call(
            player_id=player_id,
            community_id=community_id,
            command="combat.resolve",
            payload={
                "attacker": attacker,
                "defender": defender,
                "action": action,
                "turn_id": turn_id,
            },
            idempotency_key=(
                idempotency_key
                or f"combat:{turn_id}:{attacker['id']}:{defender['id']}:{action}"
            ),
        )
        result = response["payload"]
        action_key = result["action"]
        action_meta = {
            "attack": ("⚔️ Ataque", 10),
            "defend": ("🛡️ Defensa", 0),
            "special": ("✨ Especial", 18),
        }[action_key]
        return CombatResult(
            attacker=result["attacker"],
            defender=result["defender"],
            damage=int(result["damage"]),
            action=CombatAction(action_key, *action_meta),
            critical=bool(result["critical"]),
            defender_hp=int(result["defender_hp"]),
            state_version=int(response.get("state_version", 0)),
            event_ids=tuple(response.get("event_ids") or ()),
            reward_ids=tuple(response.get("reward_ids") or ()),
        )


    def combat_formula(
        self,
        *,
        attacker: dict[str, Any],
        defender: dict[str, Any],
        skill: dict[str, Any],
        turn_id: str,
        status_multiplier: float = 1.0,
        move_multiplier: float = 1.0,
        element_multiplier: float | None = None,
        player_id: int = 0,
        community_id: int = 0,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "attacker": attacker,
            "defender": defender,
            "skill": skill,
            "turn_id": turn_id,
            "status_multiplier": status_multiplier,
            "move_multiplier": move_multiplier,
            "target_max_hp": int(defender.get("max_hp", 100)),
        }
        if element_multiplier is not None:
            payload["element_multiplier"] = element_multiplier
        response = self._call(
            player_id=player_id,
            community_id=community_id,
            command="combat.resolve_formula",
            payload=payload,
            idempotency_key=(
                idempotency_key
                or f"formula:{turn_id}:{attacker['id']}:{defender['id']}:{skill['skill_id']}"
            ),
        )
        return dict(response["payload"])

    def status_resolve(
        self,
        *,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        response = self._call(
            player_id=0,
            community_id=0,
            command="status.resolve",
            payload=payload,
            idempotency_key=idempotency_key,
        )
        return dict(response["payload"])

    def evolution(self, *, level: int) -> dict[str, Any]:
        response = self._call(
            player_id=0,
            community_id=0,
            command="evolution.resolve",
            payload={"level": level},
            idempotency_key=f"evolution:{level}",
        )
        return dict(response["payload"])

    def stats(
        self,
        *,
        character: dict[str, Any],
        level: int,
        rarity: str,
        potential_seed: str | None = None,
    ) -> dict[str, Any]:
        response = self._call(
            player_id=0,
            community_id=0,
            command="stats.resolve",
            payload={
                "character": character,
                "level": level,
                "rarity": rarity,
                "potential_seed": potential_seed or "preview-neutral",
            },
            idempotency_key=(
                f"stats:{character['id']}:{level}:{rarity}:{potential_seed or 'preview-neutral'}"
            ),
        )
        return dict(response["payload"])

    def style(self, *, element: str) -> str:
        response = self._call(
            player_id=0,
            community_id=0,
            command="style.resolve",
            payload={"element": element},
            idempotency_key=f"style:{element}",
        )
        return str(response["payload"]["style"])

    def potential_score(self, *, seed: str) -> int:
        response = self._call(
            player_id=0,
            community_id=0,
            command="potential.resolve",
            payload={"potential_seed": seed},
            idempotency_key=f"potential:{seed}",
        )
        return int(response["payload"]["potential_score"])

    def progression(
        self,
        *,
        level: int,
        experience: int,
        gained: int,
        copies: int,
    ) -> dict[str, Any]:
        response = self._call(
            player_id=0,
            community_id=0,
            command="progression.resolve",
            payload={
                "level": level,
                "experience": experience,
                "gained": gained,
                "copies": copies,
            },
            idempotency_key=f"progression:{level}:{experience}:{gained}:{copies}",
        )
        return dict(response["payload"])

    def close(self) -> None:
        with self._lock:
            self._closed = True
            process = self._process
            self._process = None
            if process is None:
                return
            if process.poll() is None:
                try:
                    if process.stdin is not None:
                        process.stdin.close()
                except OSError:
                    pass
                try:
                    process.terminate()
                    process.wait(timeout=2)
                except (OSError, subprocess.TimeoutExpired):
                    process.kill()
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    try:
                        stream.close()
                    except OSError:
                        pass


def default_java_engine() -> WaifuMonJavaEngine:
    return WaifuMonJavaEngine()
