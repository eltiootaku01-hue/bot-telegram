from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

TOPICS: tuple[tuple[str, str], ...] = (
    ("Novedades", "Panel de novedades de la comunidad."),
    ("Waifu Poker", "Panel de Waifu Poker."),
    ("Galería", "Panel de la galería."),
    ("Moderación", "Panel de moderación y seguridad."),
)


class InsufficientPermissionsError(RuntimeError):
    """Raised when the Telegram bot cannot manage the forum group."""


class GroupBootstrapper:
    """Create or reconcile the canonical Telegram forum topics."""

    def __init__(self, db_path: str = "data/command_center_events.db") -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS topic_mappings (
                    chat_id INTEGER NOT NULL,
                    topic_name TEXT NOT NULL,
                    message_thread_id INTEGER NOT NULL,
                    panel_message_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (chat_id, topic_name),
                    UNIQUE (chat_id, message_thread_id)
                )
                """
            )
            conn.commit()

    def _existing_mappings(self, chat_id: int) -> dict[str, tuple[int, int]]:
        self._init_db()
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT topic_name, message_thread_id, panel_message_id "
                "FROM topic_mappings WHERE chat_id = ?",
                (chat_id,),
            ).fetchall()
        return {str(n): (int(t), int(p)) for n, t, p in rows}

    async def _permissions(self, chat_id: int, bot: Bot) -> tuple[bool, bool]:
        me = await bot.get_me()
        member = await bot.get_chat_member(chat_id, me.id)
        return (
            bool(getattr(member, "can_manage_topics", False)),
            bool(getattr(member, "can_pin_messages", False)),
        )

    @staticmethod
    def _panel(topic_name: str, panel_text: str, thread_id: int) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="Abrir panel",
                    callback_data=f"bootstrap:{thread_id}",
                )]
            ]
        )

    async def _reconcile_existing(
        self,
        chat_id: int,
        bot_instance: Bot,
        mappings: dict[str, tuple[int, int]],
    ) -> list[dict[str, int | str]]:
        reconciled: list[dict[str, int | str]] = []
        for topic_name, _ in TOPICS:
            thread_id, panel_id = mappings[topic_name]
            await bot_instance.pin_chat_message(
                chat_id=chat_id,
                message_id=panel_id,
                disable_notification=True,
            )
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "UPDATE topic_mappings SET updated_at=CURRENT_TIMESTAMP "
                    "WHERE chat_id=? AND topic_name=?",
                    (chat_id, topic_name),
                )
                conn.commit()
            reconciled.append({
                "topic_name": topic_name,
                "message_thread_id": thread_id,
                "panel_message_id": panel_id,
            })
        return reconciled

    async def run_bootstrap(self, chat_id: int, bot_instance: Bot) -> dict[str, object]:
        if chat_id == 0:
            raise ValueError("chat_id must be non-zero")

        # Consult SQLite before touching Telegram. A complete mapping is authoritative.
        existing = self._existing_mappings(chat_id)
        canonical_names = {name for name, _ in TOPICS}
        if canonical_names.issubset(existing):
            topics = await self._reconcile_existing(chat_id, bot_instance, existing)
            return {"chat_id": chat_id, "topics": topics, "reconciled": True}

        can_manage_topics, can_pin_messages = await self._permissions(chat_id, bot_instance)
        missing = []
        if not can_manage_topics:
            missing.append("can_manage_topics")
        if not can_pin_messages:
            missing.append("can_pin_messages")
        if missing:
            raise InsufficientPermissionsError(
                "Bot lacks required Telegram permissions: " + ", ".join(missing)
            )

        created: list[dict[str, int | str]] = []
        for topic_name, panel_text in TOPICS:
            # Recover partial runs without recreating already-persisted topics.
            current = self._existing_mappings(chat_id)
            if topic_name in current:
                thread_id, panel_id = current[topic_name]
                await bot_instance.pin_chat_message(
                    chat_id=chat_id,
                    message_id=panel_id,
                    disable_notification=True,
                )
            else:
                result = await bot_instance.create_forum_topic(
                    chat_id=chat_id, name=topic_name
                )
                thread_id = int(result.message_thread_id)
                panel = await bot_instance.send_message(
                    chat_id=chat_id,
                    message_thread_id=thread_id,
                    text=panel_text,
                    reply_markup=self._panel(topic_name, panel_text, thread_id),
                )
                panel_id = int(panel.message_id)
                await bot_instance.pin_chat_message(
                    chat_id=chat_id,
                    message_id=panel_id,
                    disable_notification=True,
                )
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute(
                        """
                        INSERT INTO topic_mappings
                            (chat_id, topic_name, message_thread_id, panel_message_id)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(chat_id, topic_name) DO UPDATE SET
                            message_thread_id=excluded.message_thread_id,
                            panel_message_id=excluded.panel_message_id,
                            updated_at=CURRENT_TIMESTAMP
                        """,
                        (chat_id, topic_name, thread_id, panel_id),
                    )
                    conn.commit()

            created.append({
                "topic_name": topic_name,
                "message_thread_id": thread_id,
                "panel_message_id": panel_id,
            })

        return {"chat_id": chat_id, "topics": created, "reconciled": False}
