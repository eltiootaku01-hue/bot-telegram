# -*- coding: utf-8 -*-
"""Outbox durable de Telegram, incluyendo followups independientes."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .telegram import TelegramOutbound


class TelegramOutboxError(RuntimeError):
    """Error de persistencia o integridad de la outbox."""


@dataclass(frozen=True, slots=True)
class TelegramOutboxRecord:
    update_id: int
    chat_id: str
    outbound: "TelegramOutbound"
    next_chunk: int
    status: str
    delivery_id: str = ""
    kind: str = "main"


class TelegramOutboxStore:
    """Outbox durable; cada followup tiene su propia unidad de entrega."""

    VALID_STATUSES = {"PENDING", "DELIVERED", "FAILED"}

    def __init__(self, database_path: Path | str) -> None:
        self._path = Path(database_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=15.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=15000")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _initialize(self) -> None:
        with closing(self._connection()) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS telegram_outbox (
                    update_id INTEGER PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    next_chunk INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'PENDING'
                        CHECK (status IN ('PENDING', 'DELIVERED', 'FAILED')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS ix_telegram_outbox_status
                    ON telegram_outbox(status, created_at);

                CREATE TABLE IF NOT EXISTS telegram_outbox_followups (
                    delivery_id TEXT PRIMARY KEY,
                    update_id INTEGER NOT NULL,
                    sequence INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    next_chunk INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'PENDING'
                        CHECK (status IN ('PENDING', 'DELIVERED', 'FAILED')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(update_id, sequence),
                    FOREIGN KEY(update_id)
                        REFERENCES telegram_outbox(update_id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS ix_telegram_outbox_followups_pending
                    ON telegram_outbox_followups(update_id, status, sequence);
                """
            )
            connection.commit()

    @staticmethod
    def _serialize(
        outbound: "TelegramOutbound",
        *,
        include_followups: bool = False,
    ) -> str:
        payload: dict[str, Any] = {
            "chat_id": outbound.chat_id,
            "text": outbound.text,
            "route": outbound.route,
            "keyboard": [
                [list(button) for button in row]
                for row in outbound._normalized_keyboard()
            ],
            "auto_delete_seconds": outbound.auto_delete_seconds,
            "message_thread_id": outbound.message_thread_id,
            "reply_to_message_id": outbound.reply_to_message_id,
            "photo_file_id": outbound.photo_file_id,
        }
        if include_followups:
            payload["followups"] = [
                TelegramOutboxStore._serialize_to_obj(item)
                for item in outbound.followups
            ]
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _serialize_to_obj(outbound: "TelegramOutbound") -> dict[str, object]:
        return json.loads(TelegramOutboxStore._serialize(outbound))

    @staticmethod
    def _deserialize(payload: str) -> "TelegramOutbound":
        from .telegram import TelegramOutbound

        try:
            raw = json.loads(payload)
        except json.JSONDecodeError as error:
            raise TelegramOutboxError(
                "telegram outbox payload is invalid JSON"
            ) from error
        if not isinstance(raw, dict):
            raise TelegramOutboxError(
                "telegram outbox payload must be an object"
            )

        keyboard_raw = raw.get("keyboard", [])
        if not isinstance(keyboard_raw, list):
            raise TelegramOutboxError("telegram outbox keyboard is invalid")
        keyboard: list[tuple[tuple[str, str], ...]] = []
        for row in keyboard_raw:
            if not isinstance(row, list):
                raise TelegramOutboxError(
                    "telegram outbox keyboard row is invalid"
                )
            buttons: list[tuple[str, str]] = []
            for button in row:
                if not isinstance(button, list) or len(button) != 2:
                    raise TelegramOutboxError(
                        "telegram outbox button is invalid"
                    )
                label, data = button
                if not isinstance(label, str) or not isinstance(data, str):
                    raise TelegramOutboxError(
                        "telegram outbox button values are invalid"
                    )
                buttons.append((label, data))
            keyboard.append(tuple(buttons))

        chat_id = raw.get("chat_id")
        text = raw.get("text")
        route = raw.get("route")
        auto_delete_seconds = raw.get("auto_delete_seconds")
        message_thread_id = raw.get("message_thread_id")
        reply_to_message_id = raw.get("reply_to_message_id")
        photo_file_id = raw.get("photo_file_id")

        if not isinstance(chat_id, str) or not isinstance(text, str):
            raise TelegramOutboxError(
                "telegram outbox message fields are invalid"
            )
        if route is not None and not isinstance(route, str):
            raise TelegramOutboxError("telegram outbox route is invalid")
        if auto_delete_seconds is not None and (
            not isinstance(auto_delete_seconds, int)
            or isinstance(auto_delete_seconds, bool)
        ):
            raise TelegramOutboxError(
                "telegram outbox auto-delete value is invalid"
            )
        if message_thread_id is not None and not isinstance(message_thread_id, int):
            raise TelegramOutboxError(
                "telegram outbox thread id is invalid"
            )
        if reply_to_message_id is not None and not isinstance(reply_to_message_id, int):
            raise TelegramOutboxError(
                "telegram outbox reply id is invalid"
            )
        if photo_file_id is not None and not isinstance(photo_file_id, str):
            raise TelegramOutboxError(
                "telegram outbox photo id is invalid"
            )

        return TelegramOutbound(
            chat_id,
            text,
            route,
            tuple(keyboard),
            auto_delete_seconds,
            message_thread_id,
            reply_to_message_id,
            (),
            photo_file_id,
        )

    @staticmethod
    def _validate_id(update_id: int) -> None:
        if not isinstance(update_id, int) or update_id < 0:
            raise ValueError(
                "update_id must be a non-negative integer"
            )

    @staticmethod
    def _validate_status(status: str, next_chunk: int) -> None:
        if status not in TelegramOutboxStore.VALID_STATUSES:
            raise TelegramOutboxError(
                "telegram outbox contains an invalid status"
            )
        if next_chunk < 0:
            raise TelegramOutboxError(
                "telegram outbox contains an invalid chunk offset"
            )

    def _row_to_record(self, row: sqlite3.Row, *, kind: str) -> TelegramOutboxRecord:
        status = str(row["status"])
        next_chunk = int(row["next_chunk"])
        self._validate_status(status, next_chunk)
        outbound = self._deserialize(str(row["payload"]))
        return TelegramOutboxRecord(
            int(row["update_id"]),
            str(row["chat_id"]),
            outbound,
            next_chunk,
            status,
            str(row["delivery_id"]),
            kind,
        )

    def get(self, update_id: int) -> TelegramOutboxRecord | None:
        self._validate_id(update_id)
        with closing(self._connection()) as connection:
            row = connection.execute(
                """
                SELECT update_id, chat_id, payload, next_chunk,
                       status, CAST(update_id AS TEXT) AS delivery_id
                FROM telegram_outbox
                WHERE update_id=?
                """,
                (update_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row, kind="main")

    def create_pending(
        self,
        update_id: int,
        outbound: "TelegramOutbound",
    ) -> TelegramOutboxRecord:
        self._validate_id(update_id)
        from .telegram import TelegramOutbound

        if not isinstance(outbound, TelegramOutbound):
            raise TelegramInputError("outbound is invalid")

        main = TelegramOutbound(
            outbound.chat_id,
            outbound.text,
            outbound.route,
            outbound.keyboard,
            outbound.auto_delete_seconds,
            outbound.message_thread_id,
            outbound.reply_to_message_id,
            (),
            outbound.photo_file_id,
        )

        with closing(self._connection()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    """
                    INSERT INTO telegram_outbox(
                        update_id, chat_id, payload, next_chunk, status
                    ) VALUES (?, ?, ?, 0, 'PENDING')
                    ON CONFLICT(update_id) DO UPDATE SET
                        chat_id=excluded.chat_id,
                        payload=excluded.payload,
                        next_chunk=0,
                        status='PENDING'
                    WHERE telegram_outbox.status='FAILED'
                    """,
                    (
                        update_id,
                        int(main.chat_id),
                        self._serialize(main),
                    ),
                )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise

        record = self.get(update_id)
        if record is None:
            raise TelegramOutboxError(
                "telegram outbox record disappeared after insert"
            )
        return record

    def create_followups(
        self,
        update_id: int,
        followups: tuple["TelegramOutbound", ...],
    ) -> tuple[TelegramOutboxRecord, ...]:
        self._validate_id(update_id)
        created: list[TelegramOutboxRecord] = []
        with closing(self._connection()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                parent = connection.execute(
                    "SELECT 1 FROM telegram_outbox WHERE update_id=?",
                    (update_id,),
                ).fetchone()
                if parent is None:
                    raise TelegramOutboxError(
                        "cannot create followups without main outbox item"
                    )

                for sequence, outbound in enumerate(followups):
                    delivery_id = f"{update_id}:followup:{sequence}"
                    payload = self._serialize(outbound)
                    connection.execute(
                        """
                        INSERT INTO telegram_outbox_followups(
                            delivery_id, update_id, sequence, chat_id,
                            payload, next_chunk, status
                        ) VALUES (?, ?, ?, ?, ?, 0, 'PENDING')
                        ON CONFLICT(delivery_id) DO NOTHING
                        """,
                        (
                            delivery_id,
                            update_id,
                            sequence,
                            int(outbound.chat_id),
                            payload,
                        ),
                    )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise

        with closing(self._connection()) as connection:
            rows = connection.execute(
                """
                SELECT update_id, chat_id, payload, next_chunk,
                       status, delivery_id
                FROM telegram_outbox_followups
                WHERE update_id=?
                ORDER BY sequence
                """,
                (update_id,),
            ).fetchall()
        for row in rows:
            created.append(self._row_to_record(row, kind="followup"))
        return tuple(created)

    def get_followup(
        self,
        delivery_id: str,
    ) -> TelegramOutboxRecord | None:
        with closing(self._connection()) as connection:
            row = connection.execute(
                """
                SELECT update_id, chat_id, payload, next_chunk,
                       status, delivery_id
                FROM telegram_outbox_followups
                WHERE delivery_id=?
                """,
                (str(delivery_id),),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row, kind="followup")

    def pending_for_update(
        self,
        update_id: int,
    ) -> tuple[TelegramOutboxRecord, ...]:
        self._validate_id(update_id)
        records: list[TelegramOutboxRecord] = []
        main = self.get(update_id)
        if main is not None and main.status == "PENDING":
            records.append(main)
        with closing(self._connection()) as connection:
            rows = connection.execute(
                """
                SELECT update_id, chat_id, payload, next_chunk,
                       status, delivery_id
                FROM telegram_outbox_followups
                WHERE update_id=? AND status='PENDING'
                ORDER BY sequence
                """,
                (update_id,),
            ).fetchall()
        records.extend(
            self._row_to_record(row, kind="followup")
            for row in rows
        )
        return tuple(records)

    def has_undelivered(self, update_id: int) -> bool:
        return bool(self.pending_for_update(update_id))

    def all_delivered(self, update_id: int) -> bool:
        main = self.get(update_id)
        if main is None or main.status != "DELIVERED":
            return False
        with closing(self._connection()) as connection:
            pending = connection.execute(
                """
                SELECT 1
                FROM telegram_outbox_followups
                WHERE update_id=? AND status!='DELIVERED'
                LIMIT 1
                """,
                (update_id,),
            ).fetchone()
        return pending is None

    def ack_chunk(
        self,
        update_id: int,
        next_chunk: int,
    ) -> None:
        self._ack("main", str(update_id), next_chunk)

    def ack_followup_chunk(
        self,
        delivery_id: str,
        next_chunk: int,
    ) -> None:
        self._ack("followup", str(delivery_id), next_chunk)

    def _ack(self, kind: str, delivery_id: str, next_chunk: int) -> None:
        if not isinstance(next_chunk, int) or next_chunk < 0:
            raise ValueError(
                "next_chunk must be a non-negative integer"
            )
        with closing(self._connection()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                if kind == "main":
                    cursor = connection.execute(
                        """
                        UPDATE telegram_outbox
                        SET next_chunk=?
                        WHERE update_id=? AND status='PENDING'
                              AND next_chunk<=?
                        """,
                        (
                            next_chunk,
                            int(delivery_id),
                            next_chunk,
                        ),
                    )
                else:
                    cursor = connection.execute(
                        """
                        UPDATE telegram_outbox_followups
                        SET next_chunk=?
                        WHERE delivery_id=? AND status='PENDING'
                              AND next_chunk<=?
                        """,
                        (
                            next_chunk,
                            delivery_id,
                            next_chunk,
                        ),
                    )
                if cursor.rowcount != 1:
                    raise TelegramOutboxError(
                        "telegram outbox chunk ACK was not applied"
                    )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise

    def mark_delivered(self, update_id: int) -> None:
        self._mark("main", str(update_id))

    def mark_followup_delivered(self, delivery_id: str) -> None:
        self._mark("followup", str(delivery_id))

    def _mark(self, kind: str, delivery_id: str) -> None:
        with closing(self._connection()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                if kind == "main":
                    cursor = connection.execute(
                        """
                        UPDATE telegram_outbox
                        SET status='DELIVERED'
                        WHERE update_id=? AND status='PENDING'
                        """,
                        (int(delivery_id),),
                    )
                else:
                    cursor = connection.execute(
                        """
                        UPDATE telegram_outbox_followups
                        SET status='DELIVERED'
                        WHERE delivery_id=? AND status='PENDING'
                        """,
                        (delivery_id,),
                    )
                if cursor.rowcount == 0:
                    table = (
                        "telegram_outbox"
                        if kind == "main"
                        else "telegram_outbox_followups"
                    )
                    column = "update_id" if kind == "main" else "delivery_id"
                    row = connection.execute(
                        f"SELECT status FROM {table} WHERE {column}=?",
                        (int(delivery_id) if kind == "main" else delivery_id,),
                    ).fetchone()
                    if row is not None and row["status"] == "DELIVERED":
                        connection.execute("COMMIT")
                        return
                    raise TelegramOutboxError(
                        "telegram outbox delivery transition failed"
                    )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise

    def mark_failed(self, update_id: int) -> None:
        self._mark("main", str(update_id))

    def pending_unfinished(self, limit: int = 100) -> tuple[TelegramOutboxRecord, ...]:
        if limit < 1:
            raise ValueError("limit must be positive")
        with closing(self._connection()) as connection:
            main_rows = connection.execute(
                """
                SELECT update_id, chat_id, payload, next_chunk,
                       status, CAST(update_id AS TEXT) AS delivery_id
                FROM telegram_outbox
                WHERE status='PENDING'
                ORDER BY created_at
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            followup_rows = connection.execute(
                """
                SELECT update_id, chat_id, payload, next_chunk,
                       status, delivery_id
                FROM telegram_outbox_followups
                WHERE status='PENDING'
                ORDER BY created_at, sequence
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        rows = [
            (row, "main")
            for row in main_rows
        ] + [
            (row, "followup")
            for row in followup_rows
        ]
        rows.sort(key=lambda item: str(item[0]["created_at"] if "created_at" in item[0].keys() else item[0]["delivery_id"]))
        return tuple(
            self._row_to_record(row, kind=kind)
            for row, kind in rows[:limit]
        )
