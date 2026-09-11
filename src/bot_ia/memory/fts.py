"""Índice FTS5 opcional y reconstruible para la memoria local."""
from __future__ import annotations

import sqlite3


class FTS5Unavailable(RuntimeError):
    """SQLite fue compilado sin soporte FTS5."""


class MemoryFTS:
    TABLE = "memories_fts"

    @classmethod
    def ensure(cls, connection: sqlite3.Connection) -> bool:
        try:
            connection.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5("
                "memory_id UNINDEXED, universe_id UNINDEXED, user_id UNINDEXED, "
                "conversation_id UNINDEXED, content, tags)"
            )
        except sqlite3.OperationalError as error:
            if "fts5" in str(error).lower():
                return False
            raise
        connection.executescript(
            """
            CREATE TRIGGER IF NOT EXISTS memories_fts_ai AFTER INSERT ON memories BEGIN
                INSERT INTO memories_fts(memory_id, universe_id, user_id, conversation_id, content, tags)
                VALUES (new.memory_id, new.universe_id, new.user_id, new.conversation_id, new.content, new.tags);
            END;
            CREATE TRIGGER IF NOT EXISTS memories_fts_ad AFTER DELETE ON memories BEGIN
                DELETE FROM memories_fts WHERE memory_id = old.memory_id;
            END;
            CREATE TRIGGER IF NOT EXISTS memories_fts_au AFTER UPDATE ON memories BEGIN
                DELETE FROM memories_fts WHERE memory_id = old.memory_id;
                INSERT INTO memories_fts(memory_id, universe_id, user_id, conversation_id, content, tags)
                VALUES (new.memory_id, new.universe_id, new.user_id, new.conversation_id, new.content, new.tags);
            END;
            """
        )
        count = connection.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        indexed = connection.execute("SELECT COUNT(*) FROM memories_fts").fetchone()[0]
        if count != indexed:
            connection.execute("DELETE FROM memories_fts")
            connection.execute("INSERT INTO memories_fts(memory_id, universe_id, user_id, conversation_id, content, tags) SELECT memory_id, universe_id, user_id, conversation_id, content, tags FROM memories")
        return True

    @staticmethod
    def query(connection: sqlite3.Connection, *, universe_id: str, user_id: str, conversation_id: str | None, terms: tuple[str, ...]) -> tuple[str, ...]:
        if not terms:
            return ()
        match = " AND ".join(f'"{term.replace(chr(34), chr(34) + chr(34))}"' for term in terms)
        rows = connection.execute(
            "SELECT memory_id FROM memories_fts WHERE memories_fts MATCH ? AND universe_id=? AND user_id=? "
            "AND (conversation_id IS NULL OR conversation_id=?)",
            (match, universe_id, user_id, conversation_id),
        ).fetchall()
        return tuple(row[0] for row in rows)
