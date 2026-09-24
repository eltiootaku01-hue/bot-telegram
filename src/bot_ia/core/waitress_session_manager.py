# -*- coding: utf-8 -*-
"""Gestión de turnos, sesiones, economía y tickets de la Taberna."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import threading
from collections.abc import Callable, Mapping
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from bot_ia.providers.prompt_builder import (
    SupervisorDirective,
    TavernSessionType,
    WaitressPromptProfile,
    build_chat_messages,
)


STANDARD_DURATION_SECONDS = 180
FAVORITE_DURATION_SECONDS = 300
REST_AFTER_SECONDS = 600
DUEL_COST_CHOCOLATES = 10
STANDARD_R_CARD_COST = 3
STANDARD_DAILY_FREE_USES = 2

AUTO_DELETE_DEFAULT_SECONDS = 45
AUTO_DELETE_MIN_SECONDS = 5
AUTO_DELETE_MAX_SECONDS = 300

MAX_TAVERN_MESSAGE_CHARS = 12000
MAX_TELEGRAM_ID_CHARS = 128
MAX_USERNAME_CHARS = 64
MAX_ITEM_NAME_CHARS = 128
MAX_WAITRESS_ID_CHARS = 64


class TavernError(RuntimeError):
    pass


class TavernConfigurationError(TavernError):
    pass


class WaitressUnavailableError(TavernError):
    pass


class SessionConflictError(TavernError):
    pass


class InsufficientBalanceError(TavernError):
    pass


class InventoryError(TavernError):
    pass


class SessionExpiredError(TavernError):
    pass


@dataclass(frozen=True, slots=True)
class TavernReply:
    text: str
    auto_delete_seconds: int | None = None
    keyboard: tuple[tuple[tuple[str, str], ...], ...] = ()


@dataclass(frozen=True, slots=True)
class UserInventorySnapshot:
    telegram_id: str
    username: str | None
    chocolates_balance: int
    daily_free_uses: int
    cards: tuple[tuple[str, str, int], ...]
    drinks: tuple[tuple[str, int], ...]
    specials: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class WaitressAvailability:
    waitress_id: str
    display_name: str
    role: str
    shift_type: str
    on_shift: bool
    is_busy: bool
    is_resting: bool
    status: str


@dataclass(frozen=True, slots=True)
class ActiveWaitressSession:
    session_id: int
    telegram_id: str
    waitress_id: str
    session_type: TavernSessionType
    start_time: datetime
    end_time: datetime


class WaitressSessionManager:
    """Servicio sin dependencia de Qt.

    WebChatQueueManager y las funciones de Telegram se inyectan como
    dependencias. Los envíos/borrados de Telegram se realizan en un pool
    acotado para evitar bloquear la GUI o un event loop.
    """

    def __init__(
        self,
        database_path: str | Path,
        *,
        web_queue_manager: object | None = None,
        message_sender: Callable[[str, str], object] | None = None,
        message_deleter: Callable[[str, int], object] | None = None,
        timezone_name: str = "America/Argentina/Buenos_Aires",
        now_provider: Callable[[], datetime] | None = None,
        max_notification_workers: int = 4,
    ) -> None:
        self._path = Path(database_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._tz = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as error:
            raise TavernConfigurationError(
                f"unknown tavern timezone: {timezone_name}"
            ) from error

        if max_notification_workers < 1:
            raise TavernConfigurationError("max_notification_workers must be positive")

        self._web_queue = web_queue_manager
        self._message_sender = message_sender
        self._now_provider = now_provider or (
            lambda: datetime.now(timezone.utc)
        )
        self._message_deleter = message_deleter
        self._notification_pool = ThreadPoolExecutor(
            max_workers=max_notification_workers,
            thread_name_prefix="bot-ia-tavern",
        )
        self._timers: dict[str, threading.Timer] = {}
        self._timer_lock = threading.RLock()
        self._ticket_sessions: dict[str, int] = {}
        self._ticket_lock = threading.RLock()
        self._shutdown = False

        self._initialize_database()
        self._wire_web_queue()
        self._reconcile_persisted_sessions()
        self._schedule_initial_rest_timers()

    def _initialize_database(self) -> None:
        schema_path = (
            Path(__file__).resolve().parents[1] / "memory" / "schema.sql"
        )
        with closing(sqlite3.connect(self._path, timeout=10.0)) as connection:
            connection.execute("PRAGMA busy_timeout=10000")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(
                schema_path.read_text(encoding="utf-8")
            )
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        if self._shutdown:
            raise TavernError("tavern manager is shut down")
        connection = sqlite3.connect(self._path, timeout=10.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=10000")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _transaction(self) -> sqlite3.Connection:
        connection = self._connect()
        connection.execute("BEGIN IMMEDIATE")
        return connection

    def _wire_web_queue(self) -> None:
        if self._web_queue is None:
            return
        for signal_name, callback_name in (
            ("ticket_processed", "_on_ticket_processed"),
            ("ticket_failed", "_on_ticket_failed"),
            ("ticket_started", "_on_ticket_started"),
            ("ticket_finished", "_on_ticket_finished"),
        ):
            signal = getattr(self._web_queue, signal_name, None)
            connector = getattr(signal, "connect", None)
            if callable(connector):
                connector(getattr(self, callback_name))

    def _reconcile_persisted_sessions(self) -> None:
        """Reconciles persisted active sessions and their timers after restart."""
        now = self._now_utc()

        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT session_id, waitress_id, end_time "
                "FROM active_sessions WHERE is_active=1"
            ).fetchall()

            for row in rows:
                end = datetime.fromisoformat(row["end_time"])
                if end <= now:
                    connection.execute(
                        "UPDATE active_sessions SET is_active=0 "
                        "WHERE session_id=? AND is_active=1",
                        (int(row["session_id"]),),
                    )
                    connection.execute(
                        "UPDATE waitresses SET is_busy=0, is_resting=1 "
                        "WHERE waitress_id=?",
                        (row["waitress_id"],),
                    )
                else:
                    connection.execute(
                        "UPDATE waitresses SET is_busy=1, is_resting=0 "
                        "WHERE waitress_id=?",
                        (row["waitress_id"],)
                    )
            connection.commit()

        with closing(self._connect()) as connection:
            active = connection.execute(
                "SELECT session_id, end_time "
                "FROM active_sessions WHERE is_active=1"
            ).fetchall()

        for row in active:
            end = datetime.fromisoformat(row["end_time"])
            delay = max(0.1, (end - now).total_seconds())
            self._schedule_session_expiry(
                int(row["session_id"]),
                delay,
            )

    def _schedule_initial_rest_timers(self) -> None:
        with closing(self._connect()) as connection:
            ids = tuple(
                row["waitress_id"]
                for row in connection.execute(
                    "SELECT waitress_id FROM waitresses WHERE role='novice'"
                ).fetchall()
            )
        for waitress_id in ids:
            self._reset_rest_timer(waitress_id)

    @staticmethod
    def _bounded(value: str, limit: int, name: str) -> str:
        if not isinstance(value, str):
            raise ValueError(f"{name} must be a string")
        value = value.strip()
        if not value:
            raise ValueError(f"{name} cannot be empty")
        if len(value) > limit:
            raise ValueError(f"{name} exceeds safety limit")
        return value

    def _now_utc(self) -> datetime:
        value = self._now_provider()
        if value.tzinfo is None:
            raise TavernConfigurationError(
                "now_provider must return timezone-aware datetimes"
            )
        return value.astimezone(timezone.utc)

    def _now_local(self) -> datetime:
        return self._now_utc().astimezone(self._tz)

    def _ensure_user_locked(
        self,
        connection: sqlite3.Connection,
        telegram_id: str,
        username: str | None = None,
    ) -> sqlite3.Row:
        connection.execute(
            "INSERT INTO users "
            "(telegram_id, username, chocolates_balance, daily_free_uses, last_daily_reset) "
            "VALUES (?, ?, 0, ?, NULL) "
            "ON CONFLICT(telegram_id) DO UPDATE SET "
            "username=COALESCE(excluded.username, users.username)",
            (telegram_id, username, STANDARD_DAILY_FREE_USES),
        )
        self._reset_daily_locked(connection, telegram_id)
        return connection.execute(
            "SELECT * FROM users WHERE telegram_id=?",
            (telegram_id,),
        ).fetchone()

    def _reset_daily_locked(
        self,
        connection: sqlite3.Connection,
        telegram_id: str,
    ) -> None:
        today = self._now_local().date().isoformat()
        row = connection.execute(
            "SELECT last_daily_reset FROM users WHERE telegram_id=?",
            (telegram_id,),
        ).fetchone()
        if row is None:
            raise TavernError("user does not exist")
        last_reset = row["last_daily_reset"]
        if not last_reset or str(last_reset)[:10] != today:
            connection.execute(
                "UPDATE users SET daily_free_uses=?, last_daily_reset=? "
                "WHERE telegram_id=?",
                (
                    STANDARD_DAILY_FREE_USES,
                    self._now_utc().isoformat(),
                    telegram_id,
                ),
            )

    @staticmethod
    def _is_on_shift(row: sqlite3.Row, hour: int) -> bool:
        shift_type = str(row["shift_type"])
        if shift_type == "ALL_NIGHT":
            return True
        start = int(row["shift_start_hour"])
        end = int(row["shift_end_hour"])
        if shift_type == "DAY":
            return start <= hour < end
        if shift_type == "NIGHT":
            return start <= hour < end if start < end else hour >= start or hour < end
        return False

    def list_turns(self) -> tuple[WaitressAvailability, ...]:
        hour = self._now_local().hour
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT waitress_id, display_name, role, shift_type, "
                "shift_start_hour, shift_end_hour, is_busy, is_resting "
                "FROM waitresses ORDER BY role DESC, waitress_id"
            ).fetchall()

        result: list[WaitressAvailability] = []
        for row in rows:
            on_shift = self._is_on_shift(row, hour)
            if not on_shift or bool(row["is_resting"]):
                status = "descansando"
            elif bool(row["is_busy"]):
                status = "ocupada"
            else:
                status = "libre"
            result.append(
                WaitressAvailability(
                    row["waitress_id"],
                    row["display_name"],
                    row["role"],
                    row["shift_type"],
                    on_shift,
                    bool(row["is_busy"]),
                    bool(row["is_resting"]),
                    status,
                )
            )
        return tuple(result)

    def _load_waitress_locked(
        self,
        connection: sqlite3.Connection,
        waitress_id: str,
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM waitresses WHERE waitress_id=?",
            (waitress_id,),
        ).fetchone()
        if row is None:
            raise WaitressUnavailableError("waitress does not exist")
        return row

    @staticmethod
    def _active_session_locked(
        connection: sqlite3.Connection,
        telegram_id: str,
    ) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT s.*, w.display_name "
            "FROM active_sessions s "
            "JOIN waitresses w ON w.waitress_id=s.waitress_id "
            "WHERE s.telegram_id=? AND s.is_active=1",
            (telegram_id,),
        ).fetchone()

    def _reserve_cards_r_locked(
        self,
        connection: sqlite3.Connection,
        telegram_id: str,
        amount: int,
    ) -> None:
        rows = connection.execute(
            "SELECT inventory_id, quantity FROM user_inventory "
            "WHERE telegram_id=? AND item_type='CARD' AND rarity='R' AND quantity>0 "
            "ORDER BY inventory_id",
            (telegram_id,),
        ).fetchall()
        total = sum(int(row["quantity"]) for row in rows)
        if total < amount:
            raise InsufficientBalanceError(
                f"se necesitan {amount} cartas R"
            )
        remaining = amount
        for row in rows:
            take = min(remaining, int(row["quantity"]))
            connection.execute(
                "UPDATE user_inventory SET quantity=quantity-? "
                "WHERE inventory_id=? AND quantity>=?",
                (take, row["inventory_id"], take),
            )
            remaining -= take
            if remaining == 0:
                return
        raise InsufficientBalanceError("no fue posible reservar las cartas R")

    def _consume_item_locked(
        self,
        connection: sqlite3.Connection,
        telegram_id: str,
        item_type: str,
        item_name: str,
    ) -> None:
        row = connection.execute(
            "SELECT inventory_id, quantity FROM user_inventory "
            "WHERE telegram_id=? AND item_type=? AND item_name=? AND quantity>0 "
            "ORDER BY inventory_id LIMIT 1",
            (telegram_id, item_type, item_name),
        ).fetchone()
        if row is None or int(row["quantity"]) < 1:
            raise InsufficientBalanceError(
                f"no tienes 1 x {item_name}"
            )
        cursor = connection.execute(
            "UPDATE user_inventory SET quantity=quantity-1 "
            "WHERE inventory_id=? AND quantity>=1",
            (row["inventory_id"],),
        )
        if cursor.rowcount != 1:
            raise InsufficientBalanceError(
                f"no fue posible consumir {item_name}"
            )

    def _start_session(
        self,
        telegram_id: str,
        waitress_id: str,
        *,
        session_type: TavernSessionType,
        username: str | None,
        cost_mode: str,
    ) -> ActiveWaitressSession:
        telegram_id = self._bounded(
            telegram_id,
            MAX_TELEGRAM_ID_CHARS,
            "telegram_id",
        )
        waitress_id = self._bounded(
            waitress_id,
            MAX_WAITRESS_ID_CHARS,
            "waitress_id",
        )
        connection = self._transaction()
        try:
            user = self._ensure_user_locked(
                connection,
                telegram_id,
                username,
            )
            waitress = self._load_waitress_locked(
                connection,
                waitress_id,
            )
            if waitress["role"] != "novice":
                raise WaitressUnavailableError(
                    "Mama Mia es supervisora y no atiende sesiones normales"
                )
            if not self._is_on_shift(
                waitress,
                self._now_local().hour,
            ):
                raise WaitressUnavailableError(
                    f"{waitress['display_name']} está fuera de turno y descansando"
                )
            if self._active_session_locked(
                connection,
                telegram_id,
            ) is not None:
                raise SessionConflictError(
                    "el usuario ya tiene una sesión activa"
                )
            if connection.execute(
                "SELECT session_id FROM active_sessions "
                "WHERE waitress_id=? AND is_active=1",
                (waitress_id,),
            ).fetchone():
                raise SessionConflictError(
                    "la mesera ya está atendiendo otra sesión"
                )

            if cost_mode == "daily_or_cards":
                if int(user["daily_free_uses"]) > 0:
                    cursor = connection.execute(
                        "UPDATE users SET daily_free_uses=daily_free_uses-1 "
                        "WHERE telegram_id=? AND daily_free_uses>0",
                        (telegram_id,),
                    )
                    if cursor.rowcount != 1:
                        raise InsufficientBalanceError(
                            "no fue posible consumir el uso diario"
                        )
                else:
                    self._reserve_cards_r_locked(
                        connection,
                        telegram_id,
                        STANDARD_R_CARD_COST,
                    )
            elif cost_mode == "favorite":
                self._consume_item_locked(
                    connection,
                    telegram_id,
                    "DRINK",
                    "Bebida Favorita",
                )
            else:
                raise TavernConfigurationError("unknown session cost mode")

            start = self._now_utc()
            duration = (
                STANDARD_DURATION_SECONDS
                if session_type is TavernSessionType.STANDARD_3MIN
                else FAVORITE_DURATION_SECONDS
            )
            end = start + timedelta(seconds=duration)
            cursor = connection.execute(
                "INSERT INTO active_sessions "
                "(telegram_id, waitress_id, session_type, start_time, end_time, is_active) "
                "VALUES (?, ?, ?, ?, ?, 1)",
                (
                    telegram_id,
                    waitress_id,
                    session_type.value,
                    start.isoformat(),
                    end.isoformat(),
                ),
            )
            connection.execute(
                "UPDATE waitresses SET is_resting=0, is_busy=1 "
                "WHERE waitress_id=?",
                (waitress_id,),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

        self._reset_rest_timer(waitress_id)
        self._schedule_session_expiry(
            int(cursor.lastrowid),
            duration,
        )
        return ActiveWaitressSession(
            int(cursor.lastrowid),
            telegram_id,
            waitress_id,
            session_type,
            start,
            end,
        )

    def start_standard_session(
        self,
        telegram_id: str,
        waitress_id: str,
        *,
        username: str | None = None,
    ) -> ActiveWaitressSession:
        return self._start_session(
            telegram_id,
            waitress_id,
            session_type=TavernSessionType.STANDARD_3MIN,
            username=username,
            cost_mode="daily_or_cards",
        )

    def start_favorite_session(
        self,
        telegram_id: str,
        waitress_id: str,
        *,
        username: str | None = None,
    ) -> ActiveWaitressSession:
        return self._start_session(
            telegram_id,
            waitress_id,
            session_type=TavernSessionType.FAVORITE_5MIN,
            username=username,
            cost_mode="favorite",
        )

    def _schedule_session_expiry(
        self,
        session_id: int,
        delay_seconds: float,
    ) -> None:
        key = f"session:{session_id}"
        with self._timer_lock:
            old = self._timers.pop(key, None)
            if old is not None:
                old.cancel()
            timer = threading.Timer(
                max(0.1, delay_seconds),
                self._expire_session_safe,
                args=(session_id, key),
            )
            timer.daemon = True
            self._timers[key] = timer
            timer.start()

    def _expire_session_safe(
        self,
        session_id: int,
        key: str,
    ) -> None:
        with self._timer_lock:
            self._timers.pop(key, None)
        try:
            self.expire_session(session_id)
        except Exception:
            return

    def get_active_session(
        self,
        telegram_id: str,
    ) -> ActiveWaitressSession | None:
        telegram_id = self._bounded(
            telegram_id,
            MAX_TELEGRAM_ID_CHARS,
            "telegram_id",
        )
        with closing(self._connect()) as connection:
            row = self._active_session_locked(
                connection,
                telegram_id,
            )
        if row is None:
            return None

        start = datetime.fromisoformat(row["start_time"])
        end = datetime.fromisoformat(row["end_time"])
        if end <= self._now_utc():
            self.expire_session(int(row["session_id"]))
            return None

        return ActiveWaitressSession(
            int(row["session_id"]),
            telegram_id,
            row["waitress_id"],
            TavernSessionType(row["session_type"]),
            start,
            end,
        )

    def _directives_for(
        self,
        connection: sqlite3.Connection,
        waitress_id: str,
    ) -> tuple[SupervisorDirective, ...]:
        rows = connection.execute(
            "SELECT directive_id, directive_text FROM supervisor_directives "
            "WHERE target_waitress_id=? AND is_active=1 "
            "ORDER BY directive_id DESC LIMIT 16",
            (waitress_id,),
        ).fetchall()
        return tuple(
            SupervisorDirective(
                directive_id=f"mama-{waitress_id}-{row['directive_id']}",
                text=str(row["directive_text"]),
                priority=80,
            )
            for row in rows
        )

    def queue_user_message(
        self,
        telegram_id: str,
        user_message: str,
        *,
        user_context: str = "",
    ) -> str:
        telegram_id = self._bounded(
            telegram_id,
            MAX_TELEGRAM_ID_CHARS,
            "telegram_id",
        )
        user_message = self._bounded(
            user_message,
            MAX_TAVERN_MESSAGE_CHARS,
            "user_message",
        )
        if not self._web_queue:
            raise TavernConfigurationError(
                "WebChatQueueManager is not configured"
            )

        session = self.get_active_session(telegram_id)
        if session is None:
            raise SessionExpiredError("no active tavern session")

        connection = self._transaction()
        try:
            waitress = self._load_waitress_locked(
                connection,
                session.waitress_id,
            )
            directives = self._directives_for(
                connection,
                session.waitress_id,
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

        profile = WaitressPromptProfile(
            waitress_id=session.waitress_id,
            display_name=str(waitress["display_name"]),
            role=str(waitress["role"]),
            personality_prompt=str(waitress["personality_prompt"]),
        )
        messages = build_chat_messages(
            profile,
            session_type=session.session_type,
            user_message=user_message,
            active_directives=directives,
            user_context=user_context,
        )
        prompt = messages[0]["content"] + "\n\n" + messages[1]["content"]

        ticket_id = (
            f"tavern-{session.session_id}-{uuid4().hex[:20]}"
        )
        with self._ticket_lock:
            if self._shutdown:
                raise TavernError("tavern manager is shut down")
            self._ticket_sessions[ticket_id] = session.session_id

        try:
            self._web_queue.enqueue_bot_message(
                bot_name=str(waitress["display_name"]),
                ticket_id=ticket_id,
                action="tavern_chat",
                message=prompt,
                user=telegram_id,
                channel=f"/taberna/{session.waitress_id}",
            )
        except Exception:
            with self._ticket_lock:
                self._ticket_sessions.pop(ticket_id, None)
            raise
        return ticket_id

    def add_chocolates(
        self,
        telegram_id: str,
        amount: int,
    ) -> int:
        telegram_id = self._bounded(
            telegram_id,
            MAX_TELEGRAM_ID_CHARS,
            "telegram_id",
        )
        if not 0 <= amount <= 1_000_000:
            raise TavernError("invalid chocolate amount")
        connection = self._transaction()
        try:
            self._ensure_user_locked(connection, telegram_id)
            connection.execute(
                "UPDATE users SET chocolates_balance=chocolates_balance+? "
                "WHERE telegram_id=?",
                (amount, telegram_id),
            )
            balance = int(
                connection.execute(
                    "SELECT chocolates_balance FROM users WHERE telegram_id=?",
                    (telegram_id,),
                ).fetchone()["chocolates_balance"]
            )
            connection.commit()
            return balance
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def add_inventory(
        self,
        telegram_id: str,
        *,
        item_type: str,
        item_name: str,
        rarity: str,
        quantity: int = 1,
    ) -> None:
        telegram_id = self._bounded(
            telegram_id,
            MAX_TELEGRAM_ID_CHARS,
            "telegram_id",
        )
        item_type = self._bounded(item_type, 16, "item_type").upper()
        rarity = self._bounded(rarity, 8, "rarity").upper()
        item_name = self._bounded(
            item_name,
            MAX_ITEM_NAME_CHARS,
            "item_name",
        )
        if item_type not in {"CARD", "DRINK", "SPECIAL"}:
            raise InventoryError("invalid item_type")
        if rarity not in {"N", "R", "SR", "SSR"}:
            raise InventoryError("invalid rarity")
        if not 1 <= quantity <= 1000:
            raise InventoryError("invalid quantity")

        connection = self._transaction()
        try:
            self._ensure_user_locked(connection, telegram_id)
            connection.execute(
                "INSERT INTO user_inventory "
                "(telegram_id, item_type, item_name, rarity, quantity) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(telegram_id, item_type, item_name, rarity) "
                "DO UPDATE SET quantity=quantity+excluded.quantity",
                (
                    telegram_id,
                    item_type,
                    item_name,
                    rarity,
                    quantity,
                ),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def inventory(
        self,
        telegram_id: str,
    ) -> UserInventorySnapshot:
        telegram_id = self._bounded(
            telegram_id,
            MAX_TELEGRAM_ID_CHARS,
            "telegram_id",
        )
        connection = self._transaction()
        try:
            user_row = self._ensure_user_locked(
                connection,
                telegram_id,
            )
            rows = connection.execute(
                "SELECT item_type, item_name, rarity, quantity "
                "FROM user_inventory "
                "WHERE telegram_id=? AND quantity>0 "
                "ORDER BY item_type, rarity DESC, item_name",
                (telegram_id,),
            ).fetchall()
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

        cards = tuple(
            (row["item_name"], row["rarity"], int(row["quantity"]))
            for row in rows
            if row["item_type"] == "CARD"
        )
        drinks = tuple(
            (row["item_name"], int(row["quantity"]))
            for row in rows
            if row["item_type"] == "DRINK"
        )
        specials = tuple(
            (row["item_name"], int(row["quantity"]))
            for row in rows
            if row["item_type"] == "SPECIAL"
        )
        return UserInventorySnapshot(
            telegram_id=telegram_id,
            username=user_row["username"],
            chocolates_balance=int(user_row["chocolates_balance"]),
            daily_free_uses=int(user_row["daily_free_uses"]),
            cards=cards,
            drinks=drinks,
            specials=specials,
        )

    def charge_duel(
        self,
        telegram_id: str,
        *,
        opponent: str = "mama_mia",
    ) -> TavernReply:
        telegram_id = self._bounded(
            telegram_id,
            MAX_TELEGRAM_ID_CHARS,
            "telegram_id",
        )
        opponent = self._bounded(opponent, 128, "opponent")

        connection = self._transaction()
        try:
            self._ensure_user_locked(connection, telegram_id)
            cursor = connection.execute(
                "UPDATE users SET chocolates_balance=chocolates_balance-? "
                "WHERE telegram_id=? AND chocolates_balance>=?",
                (
                    DUEL_COST_CHOCOLATES,
                    telegram_id,
                    DUEL_COST_CHOCOLATES,
                ),
            )
            if cursor.rowcount != 1:
                raise InsufficientBalanceError(
                    f"se necesitan {DUEL_COST_CHOCOLATES} chocolates"
                )
            balance = int(
                connection.execute(
                    "SELECT chocolates_balance FROM users WHERE telegram_id=?",
                    (telegram_id,),
                ).fetchone()["chocolates_balance"]
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

        return TavernReply(
            f"💥 Desafío enviado a {opponent}. Coste: "
            f"{DUEL_COST_CHOCOLATES} chocolates. "
            f"Saldo restante: {balance}.",
            AUTO_DELETE_DEFAULT_SECONDS,
        )

    def command(
        self,
        telegram_id: str,
        command_text: str,
        *,
        username: str | None = None,
    ) -> TavernReply:
        raw = self._bounded(command_text, 512, "command_text")
        parts = raw.split()
        command = parts[0].casefold()
        args = parts[1:]

        if command == "/inventario":
            snapshot = self.inventory(telegram_id)
            cards = "\n".join(
                f"• {name} [{rarity}] x{quantity}"
                for name, rarity, quantity in snapshot.cards
            ) or "• Sin cartas"
            drinks = "\n".join(
                f"• {name} x{quantity}"
                for name, quantity in snapshot.drinks
            ) or "• Sin bebidas"
            specials = "\n".join(
                f"• {name} x{quantity}"
                for name, quantity in snapshot.specials
            ) or "• Sin objetos especiales"
            return TavernReply(
                "🥤 VASO DE CHOCOLATADA\n\n"
                f"🍫 Chocolates: {snapshot.chocolates_balance}\n"
                f"🎟️ Usos gratis de hoy: {snapshot.daily_free_uses}\n\n"
                f"🃏 Cartas:\n{cards}\n\n"
                f"🍹 Bebidas:\n{drinks}\n\n"
                f"⭐ Especiales:\n{specials}",
                AUTO_DELETE_DEFAULT_SECONDS,
            )

        if command == "/turnos":
            turns = self.list_turns()
            lines = ["📜 MENÚ DE LA CASA", ""]
            for item in turns:
                cost = (
                    "supervisión interna"
                    if item.role == "supervisor"
                    else "3 min: 1 uso diario o 3 cartas R | VIP: 1 Bebida Favorita"
                )
                lines.append(
                    f"• {item.display_name}: {item.status} — {cost}"
                )
            return TavernReply(
                "\n".join(lines),
                AUTO_DELETE_DEFAULT_SECONDS,
            )

        if command == "/duelo":
            opponent = args[0] if args else "mama_mia"
            return self.charge_duel(
                telegram_id,
                opponent=opponent,
            )

        if command in {"/ayuda_taberna", "/guia"}:
            return TavernReply(
                "🍽️ GUÍA DE LA TABERNA\n\n"
                "/turnos — horarios y estado de las meseras.\n"
                "/inventario — chocolates, cartas y bebidas.\n"
                "/duelo @usuario — desafío por 10 chocolates.\n"
                "/charla cari — charla tradicional de 3 minutos.\n"
                "/favorita cari — VIP de 5 minutos por 1 Bebida Favorita.\n"
                "Las meseras descansan después de 10 minutos sin tickets y las "
                "notificaciones temporales pueden borrarse automáticamente.",
                60,
            )

        if command in {"/charla", "/tradicional"}:
            if not args:
                raise WaitressUnavailableError(
                    "uso: /charla cari"
                )
            self.start_standard_session(
                telegram_id,
                args[0],
                username=username,
            )
            return TavernReply(
                f"🍹 Charla Tradicional iniciada con {args[0]}. "
                "Tienes 3 minutos; escribe tu mensaje para la mesera.",
                AUTO_DELETE_DEFAULT_SECONDS,
            )

        if command in {"/favorita", "/vip"}:
            if not args:
                raise WaitressUnavailableError(
                    "uso: /favorita cari"
                )
            self.start_favorite_session(
                telegram_id,
                args[0],
                username=username,
            )
            return TavernReply(
                f"🍸 Bebida Favorita iniciada con {args[0]}. "
                "Tienes 5 minutos; disfruta la charla.",
                AUTO_DELETE_DEFAULT_SECONDS,
            )

        raise TavernError("unknown tavern command")

    def send_temporary_message(
        self,
        chat_id: str,
        text: str,
        *,
        auto_delete_seconds: int = AUTO_DELETE_DEFAULT_SECONDS,
    ) -> None:
        chat_id = self._bounded(chat_id, MAX_TELEGRAM_ID_CHARS, "chat_id")
        text = self._bounded(text, MAX_TAVERN_MESSAGE_CHARS, "text")
        if not self._message_sender:
            raise TavernConfigurationError(
                "message_sender is not configured"
            )
        if not AUTO_DELETE_MIN_SECONDS <= auto_delete_seconds <= AUTO_DELETE_MAX_SECONDS:
            raise ValueError("auto_delete_seconds out of range")
        self._submit_notification(
            chat_id,
            text,
            auto_delete_seconds=auto_delete_seconds,
        )

    def _submit_notification(
        self,
        chat_id: str,
        text: str,
        *,
        auto_delete_seconds: int = AUTO_DELETE_DEFAULT_SECONDS,
    ) -> None:
        if self._shutdown:
            return
        try:
            self._notification_pool.submit(
                self._send_notification,
                chat_id,
                text,
                auto_delete_seconds,
            )
        except RuntimeError:
            return

    def _send_notification(
        self,
        chat_id: str,
        text: str,
        auto_delete_seconds: int,
    ) -> None:
        if self._message_sender is None:
            return
        try:
            result = self._message_sender(chat_id, text)
            message_id = self._extract_message_id(result)
            if message_id is not None:
                self.schedule_auto_delete(
                    chat_id,
                    message_id,
                    seconds=auto_delete_seconds,
                )
        except Exception:
            return

    @staticmethod
    def _extract_message_id(result: object) -> int | None:
        if isinstance(result, bool):
            return None
        if isinstance(result, int):
            return result
        if isinstance(result, Mapping):
            value = result.get("message_id")
            if isinstance(value, int):
                return value
            nested = result.get("result")
            if isinstance(nested, Mapping):
                value = nested.get("message_id")
                if isinstance(value, int):
                    return value
        return None

    def schedule_auto_delete(
        self,
        chat_id: str,
        message_id: int,
        *,
        seconds: int = AUTO_DELETE_DEFAULT_SECONDS,
    ) -> None:
        chat_id = self._bounded(chat_id, MAX_TELEGRAM_ID_CHARS, "chat_id")
        if not AUTO_DELETE_MIN_SECONDS <= seconds <= AUTO_DELETE_MAX_SECONDS:
            raise ValueError("auto-delete seconds out of range")
        key = f"delete:{chat_id}:{message_id}"
        with self._timer_lock:
            old = self._timers.pop(key, None)
            if old is not None:
                old.cancel()
            timer = threading.Timer(
                seconds,
                self._enqueue_delete,
                args=(chat_id, message_id, key),
            )
            timer.daemon = True
            self._timers[key] = timer
            timer.start()

    def _enqueue_delete(
        self,
        chat_id: str,
        message_id: int,
        key: str,
    ) -> None:
        with self._timer_lock:
            self._timers.pop(key, None)
        if self._shutdown or self._message_deleter is None:
            return
        try:
            self._notification_pool.submit(
                self._delete_message_safe,
                chat_id,
                message_id,
            )
        except RuntimeError:
            return

    def _delete_message_safe(
        self,
        chat_id: str,
        message_id: int,
    ) -> None:
        if self._message_deleter is None:
            return
        try:
            self._message_deleter(chat_id, message_id)
        except Exception:
            return

    def _on_ticket_started(
        self,
        ticket_id: str,
        _bot_name: str,
    ) -> None:
        with self._ticket_lock:
            session_id = self._ticket_sessions.get(ticket_id)
        if session_id is not None:
            self._set_waitress_state(
                session_id,
                busy=True,
                resting=False,
            )

    def _on_ticket_processed(
        self,
        ticket_id: str,
        response_text: str,
    ) -> None:
        with self._ticket_lock:
            session_id = self._ticket_sessions.get(ticket_id)
        if session_id is None:
            return
        session = self._session_by_id(session_id)
        if session is None:
            return
        self._submit_notification(
            session.telegram_id,
            response_text,
        )

    def _on_ticket_failed(
        self,
        ticket_id: str,
        _reason: str,
    ) -> None:
        with self._ticket_lock:
            session_id = self._ticket_sessions.pop(ticket_id, None)
        if session_id is None:
            return
        session = self._session_by_id(session_id)
        if session is not None:
            self._set_waitress_state(
                session_id,
                busy=True,
                resting=False,
            )
            self._reset_rest_timer(session.waitress_id)
            self._submit_notification(
                session.telegram_id,
                "La mesera tuvo un problema con la charla. No se descontará otro coste por este fallo.",
            )

    def _on_ticket_finished(
        self,
        ticket_id: str,
        _bot_name: str,
    ) -> None:
        with self._ticket_lock:
            session_id = self._ticket_sessions.pop(ticket_id, None)
        if session_id is None:
            return
        session = self._session_by_id(session_id)
        if session is not None:
            self._set_waitress_state(
                session_id,
                busy=True,
                resting=False,
            )
            self._reset_rest_timer(session.waitress_id)

    def _session_by_id(
        self,
        session_id: int,
    ) -> ActiveWaitressSession | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT session_id, telegram_id, waitress_id, "
                "session_type, start_time, end_time "
                "FROM active_sessions "
                "WHERE session_id=? AND is_active=1",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return ActiveWaitressSession(
            int(row["session_id"]),
            row["telegram_id"],
            row["waitress_id"],
            TavernSessionType(row["session_type"]),
            datetime.fromisoformat(row["start_time"]),
            datetime.fromisoformat(row["end_time"]),
        )

    def _set_waitress_state(
        self,
        session_id: int,
        *,
        busy: bool,
        resting: bool,
    ) -> None:
        connection = self._transaction()
        try:
            row = connection.execute(
                "SELECT waitress_id FROM active_sessions WHERE session_id=?",
                (session_id,),
            ).fetchone()
            if row is not None:
                connection.execute(
                    "UPDATE waitresses SET is_busy=?, is_resting=? "
                    "WHERE waitress_id=?",
                    (
                        int(busy),
                        int(resting),
                        row["waitress_id"],
                    ),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def expire_session(self, session_id: int) -> bool:
        connection = self._transaction()
        try:
            row = connection.execute(
                "SELECT telegram_id, waitress_id "
                "FROM active_sessions "
                "WHERE session_id=? AND is_active=1",
                (session_id,),
            ).fetchone()
            if row is None:
                connection.commit()
                return False
            connection.execute(
                "UPDATE active_sessions SET is_active=0 "
                "WHERE session_id=? AND is_active=1",
                (session_id,),
            )
            connection.execute(
                "UPDATE waitresses SET is_busy=0, is_resting=1 "
                "WHERE waitress_id=?",
                (row["waitress_id"],),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

        with self._ticket_lock:
            stale = [
                ticket_id
                for ticket_id, stored_id in self._ticket_sessions.items()
                if stored_id == session_id
            ]
            for ticket_id in stale:
                self._ticket_sessions.pop(ticket_id, None)

        self._cancel_rest_timer(row["waitress_id"])
        self._submit_notification(
            row["telegram_id"],
            "⏰ La charla terminó. La mesera vuelve a la barra a descansar.",
        )
        return True

    def _reset_rest_timer(self, waitress_id: str) -> None:
        self._cancel_rest_timer(waitress_id)
        key = f"rest:{waitress_id}"
        with self._timer_lock:
            timer = threading.Timer(
                REST_AFTER_SECONDS,
                self._mark_resting_if_idle,
                args=(waitress_id, key),
            )
            timer.daemon = True
            self._timers[key] = timer
            timer.start()

    def _cancel_rest_timer(self, waitress_id: str) -> None:
        with self._timer_lock:
            timer = self._timers.pop(
                f"rest:{waitress_id}",
                None,
            )
            if timer is not None:
                timer.cancel()

    def _mark_resting_if_idle(
        self,
        waitress_id: str,
        key: str,
    ) -> None:
        with self._timer_lock:
            self._timers.pop(key, None)
        if self._shutdown:
            return
        try:
            connection = self._transaction()
            try:
                active = connection.execute(
                    "SELECT 1 FROM active_sessions "
                    "WHERE waitress_id=? AND is_active=1",
                    (waitress_id,),
                ).fetchone()
                if active is None:
                    connection.execute(
                        "UPDATE waitresses SET is_busy=0, is_resting=1 "
                        "WHERE waitress_id=?",
                        (waitress_id,),
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()
        except Exception:
            return

    def remaining_seconds(self, telegram_id: str) -> int:
        session = self.get_active_session(telegram_id)
        if session is None:
            return 0
        return max(
            0,
            int(
                (session.end_time - self._now_utc()).total_seconds()
            ),
        )

    def shutdown(self) -> None:
        if self._shutdown:
            return
        self._shutdown = True

        with self._timer_lock:
            timers = tuple(self._timers.values())
            self._timers.clear()
        for timer in timers:
            timer.cancel()

        self._notification_pool.shutdown(
            wait=False,
            cancel_futures=True,
        )
        with self._ticket_lock:
            self._ticket_sessions.clear()
