from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class TopicMapping:
    chat_id: int | None
    topic_name: str
    message_thread_id: int
    panel_message_id: int | None = None


class DynamicTopicMapper:
    """SQLite-first topic resolver with deterministic static fallback."""

    def __init__(self, db_path: str = "data/command_center_events.db",
                 static_path: str | Path = "config/forum_topics.json") -> None:
        self.db_path = db_path
        self.static_path = Path(static_path)

    def _dynamic(self, chat_id: int, topic_name: str) -> TopicMapping | None:
        if not Path(self.db_path).exists():
            return None
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT topic_name, message_thread_id, panel_message_id "
                "FROM topic_mappings WHERE chat_id=? AND topic_name=?",
                (chat_id, topic_name),
            ).fetchone()
        if row is None:
            return None
        return TopicMapping(chat_id, str(row[0]), int(row[1]), int(row[2]))

    def resolve(self, chat_id: int, topic_name: str) -> TopicMapping | None:
        """Return bootstrap-generated mapping first, then static configuration."""
        dynamic = self._dynamic(chat_id, topic_name)
        if dynamic is not None:
            return dynamic
        if not self.static_path.exists():
            return None
        data = json.loads(self.static_path.read_text(encoding="utf-8"))
        raw = data.get("topics", {}) if isinstance(data, dict) else {}
        for key, value in raw.items():
            if str(value.get("zone", "")).casefold() == topic_name.casefold()                     or str(key).casefold() == topic_name.casefold():
                return TopicMapping(None, str(key), int(value["thread_id"]))
        return None

    def for_chat(self, chat_id: int) -> dict[str, TopicMapping]:
        """Resolve all persisted topics for a bootstrapped chat."""
        if not Path(self.db_path).exists():
            return {}
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT topic_name, message_thread_id, panel_message_id "
                "FROM topic_mappings WHERE chat_id=? ORDER BY topic_name",
                (chat_id,),
            ).fetchall()
        return {
            str(row[0]): TopicMapping(chat_id, str(row[0]), int(row[1]), int(row[2]))
            for row in rows
        }
