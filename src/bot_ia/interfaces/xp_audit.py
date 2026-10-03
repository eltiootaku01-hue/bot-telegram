# -*- coding: utf-8 -*-
"""XP pasivo y auditoría centralizada, sin bloquear los handlers de chat."""
from __future__ import annotations

from contextlib import closing
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Queue
from typing import Any


@dataclass(frozen=True, slots=True)
class XPResult:
    user_id: str
    platform: str
    xp: int
    level: int
    granted: bool
    role: str | None = None


RANKS = (
    (1, "Nakama"),
    (5, "Nakama Activo"),
    (10, "Nakama Veterano"),
    (20, "Maestro del Café"),
)


class PassiveXPTrackerDrainError(RuntimeError):
    """Indica que uno o más items aceptados no pudieron persistirse durante el drain."""

    def __init__(self, failure_count: int, first_error: Exception) -> None:
        self.failure_count = int(failure_count)
        self.first_error = first_error
        super().__init__(
            "PassiveXPTracker drain failed after "
            f"{self.failure_count} persistence failure(s)"
        )


class PassiveXPTracker:
    """SQLite WAL + cola; el mensaje nunca espera una escritura SQLite."""

    def __init__(self, path: str | Path, *, cooldown_seconds: float = 60.0) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.cooldown_seconds = float(cooldown_seconds)
        self._queue: Queue[tuple[str, str, float]] = Queue()
        self._last: dict[tuple[str, str], float] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._init_db()
        self._thread: threading.Thread | None = None
        self._drain_failure_count = 0
        self._first_drain_error: Exception | None = None

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=2.0)
        db.execute("PRAGMA journal_mode=WAL")
        return db

    def _init_db(self) -> None:
        with closing(self._connect()) as db:
            db.execute("CREATE TABLE IF NOT EXISTS xp_users (user_id TEXT NOT NULL, platform TEXT NOT NULL, xp INTEGER NOT NULL DEFAULT 0, messages INTEGER NOT NULL DEFAULT 0, updated_at REAL NOT NULL, PRIMARY KEY(user_id, platform))")
            db.execute("CREATE TABLE IF NOT EXISTS audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, platform TEXT NOT NULL, user_id TEXT, event TEXT NOT NULL, details TEXT NOT NULL, created_at REAL NOT NULL)")
            db.commit()

    @staticmethod
    def level_for(xp: int) -> int:
        return max(1, int(xp) // 100 + 1)

    @staticmethod
    def role_for(level: int) -> str:
        role = "Nakama"
        for minimum, name in RANKS:
            if level >= minimum:
                role = name
        return role

    def record_message(self, user_id: str, platform: str) -> XPResult:
        now = time.monotonic()
        key = (str(user_id), str(platform).casefold())
        with self._lock:
            previous = self._last.get(key, float("-inf"))
            if now - previous < self.cooldown_seconds:
                level = self.level_for(self.current_xp(*key))
                return XPResult(key[0], key[1], 0, level, False, self.role_for(level))
            if self._stop.is_set():
                raise RuntimeError("PassiveXPTracker is stopped")
            self._ensure_writer_started_locked()
            self._queue.put((key[0], key[1], now))
            self._last[key] = now
        level = self.level_for(self.current_xp(*key) + 10)
        return XPResult(key[0], key[1], 10, level, True, self.role_for(level))

    def _ensure_writer_started(self) -> None:
        with self._lock:
            self._ensure_writer_started_locked()

    def _ensure_writer_started_locked(self) -> None:
        thread = self._thread
        if thread is not None and thread.is_alive():
            return
        if self._stop.is_set():
            raise RuntimeError("PassiveXPTracker is stopped")
        thread = threading.Thread(
            target=self._writer,
            name="nakama-xp-writer",
            daemon=True,
        )
        self._thread = thread
        thread.start()

    def current_xp(self, user_id: str, platform: str) -> int:
        with closing(self._connect()) as db:
            row = db.execute("SELECT xp FROM xp_users WHERE user_id=? AND platform=?", (user_id, platform)).fetchone()
        return int(row[0]) if row else 0

    def _writer(self) -> None:
        while True:
            if self._stop.is_set() and self._queue.empty():
                return
            try:
                user_id, platform, now = self._queue.get(timeout=0.05)
            except Empty:
                continue

            try:
                with closing(self._connect()) as db:
                    db.execute(
                        "INSERT INTO xp_users(user_id,platform,xp,messages,updated_at) "
                        "VALUES(?,?,10,1,?) "
                        "ON CONFLICT(user_id,platform) DO UPDATE SET "
                        "xp=xp+10,messages=messages+1,updated_at=excluded.updated_at",
                        (user_id, platform, now),
                    )
                    db.commit()
            except Exception as error:
                with self._lock:
                    self._drain_failure_count += 1
                    if self._first_drain_error is None:
                        self._first_drain_error = error
            finally:
                self._queue.task_done()

    def audit(self, platform: str, user_id: str, event: str, details: str) -> None:
        with closing(self._connect()) as db:
            db.execute("INSERT INTO audit_log(platform,user_id,event,details,created_at) VALUES(?,?,?,?,?)", (platform, user_id, event, details, time.time()))
            db.commit()

    def stop(self) -> None:
        with self._lock:
            self._stop.set()
            thread = self._thread

        if thread is not None and thread is not threading.current_thread():
            self._queue.join()
            thread.join()

        with self._lock:
            failure_count = self._drain_failure_count
            first_error = self._first_drain_error

        if failure_count:
            if first_error is None:
                raise RuntimeError(
                    "PassiveXPTracker recorded a drain failure without an error"
                )
            raise PassiveXPTrackerDrainError(
                failure_count,
                first_error,
            ) from first_error


class AuditBus:
    """Fan-out no bloqueante para GUI y canal interno."""

    def __init__(self) -> None:
        self._subscribers: list[Any] = []
        self._lock = threading.Lock()

    def subscribe(self, callback: Any) -> None:
        with self._lock:
            self._subscribers.append(callback)

    def publish(self, event: str, **details: object) -> None:
        with self._lock:
            subscribers = tuple(self._subscribers)
        for callback in subscribers:
            try:
                callback(event, details)
            except Exception:
                continue
