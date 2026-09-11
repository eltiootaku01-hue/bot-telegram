"""Índice FTS5 opcional y reconstruible para la memoria local."""
from __future__ import annotations

import sqlite3

from .retrieval_policy import candidate_budget


class FTS5Unavailable(RuntimeError):
    """SQLite fue compilado sin soporte FTS5."""


class MemoryFTS:
    TABLE = "memories_fts"

    @classmethod
    def ensure(cls, connection: sqlite3.Connection) -> bool:
        """Ensure the disposable index exists and is synchronized by memory id."""
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
        missing = connection.execute(
            "SELECT memory_id FROM memories EXCEPT SELECT memory_id FROM memories_fts LIMIT 1"
        ).fetchone()
        extra = connection.execute(
            "SELECT memory_id FROM memories_fts EXCEPT SELECT memory_id FROM memories LIMIT 1"
        ).fetchone()
        if missing is not None or extra is not None:
            cls.rebuild(connection)
        return True

    @classmethod
    def rebuild(cls, connection: sqlite3.Connection) -> None:
        """Rebuild the disposable projection entirely from the source table."""
        connection.execute("DELETE FROM memories_fts")
        connection.execute(
            "INSERT INTO memories_fts(memory_id, universe_id, user_id, conversation_id, content, tags) "
            "SELECT memory_id, universe_id, user_id, conversation_id, content, tags FROM memories"
        )

    @staticmethod
    def query(
        connection: sqlite3.Connection,
        *,
        universe_id: str,
        user_id: str,
        conversation_id: str | None,
        terms: tuple[str, ...],
        budget: int | None = None,
    ) -> tuple[str, ...]:
        """Return scoped, bounded candidates; deterministic ranking remains above this layer."""
        if not terms:
            return ()
        match = " OR ".join(
            f'"{term.replace(chr(34), chr(34) + chr(34))}"' for term in terms
        )
        rows = connection.execute(
            "SELECT memory_id FROM memories_fts WHERE memories_fts MATCH ? "
            "AND universe_id=? AND user_id=? "
            "AND (conversation_id IS NULL OR conversation_id=?) "
            "ORDER BY bm25(memories_fts), rowid LIMIT ?",
            (match, universe_id, user_id, conversation_id, candidate_budget(budget)),
        ).fetchall()
        return tuple(row[0] for row in rows)
