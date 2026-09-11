"""Optional local FTS5 index for memory retrieval."""
from __future__ import annotations
import sqlite3


class MemorySearchIndex:
    """Rebuildable FTS5 projection; SQLite memories remain authoritative."""
    TABLE = "memory_fts"
    MAP_TABLE = "memory_fts_map"

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.available = self._probe(connection)
        if self.available:
            self._ensure_schema(connection)

    @staticmethod
    def _probe(connection: sqlite3.Connection) -> bool:
        try:
            connection.execute("CREATE VIRTUAL TABLE temp.bot_ia_fts_probe USING fts5(value)")
            connection.execute("DROP TABLE temp.bot_ia_fts_probe")
            return True
        except sqlite3.Error:
            return False

    def _ensure_schema(self, connection: sqlite3.Connection) -> None:
        connection.execute(f"CREATE TABLE IF NOT EXISTS {self.MAP_TABLE} (memory_id TEXT PRIMARY KEY, fts_rowid INTEGER UNIQUE NOT NULL)")
        connection.execute(f"CREATE VIRTUAL TABLE IF NOT EXISTS {self.TABLE} USING fts5(content, tags, content='', contentless_delete=1)")
        connection.execute(f"INSERT INTO {self.TABLE}({self.TABLE}, rank) VALUES('secure-delete', 1)")

    def index(self, connection: sqlite3.Connection, memory_id: str, content: str, tags: str) -> None:
        if not self.available:
            return
        existing = connection.execute(f"SELECT fts_rowid FROM {self.MAP_TABLE} WHERE memory_id=?", (memory_id,)).fetchone()
        if existing is not None:
            connection.execute(f"DELETE FROM {self.TABLE} WHERE rowid=?", (existing[0],))
            connection.execute(f"DELETE FROM {self.MAP_TABLE} WHERE memory_id=?", (memory_id,))
        cursor = connection.execute(f"INSERT INTO {self.TABLE}(content, tags) VALUES (?, ?)", (content, tags))
        connection.execute(f"INSERT INTO {self.MAP_TABLE}(memory_id, fts_rowid) VALUES (?, ?)", (memory_id, cursor.lastrowid))

    def remove(self, connection: sqlite3.Connection, memory_id: str) -> None:
        if not self.available:
            return
        row = connection.execute(f"SELECT fts_rowid FROM {self.MAP_TABLE} WHERE memory_id=?", (memory_id,)).fetchone()
        if row is not None:
            connection.execute(f"DELETE FROM {self.TABLE} WHERE rowid=?", (row[0],))
            connection.execute(f"DELETE FROM {self.MAP_TABLE} WHERE memory_id=?", (memory_id,))

    def candidate_ids(self, connection: sqlite3.Connection, query: str, limit: int = 50) -> tuple[str, ...]:
        if not self.available or not query.strip():
            return ()
        rows = connection.execute(f"SELECT m.memory_id FROM {self.TABLE} f JOIN {self.MAP_TABLE} m ON m.fts_rowid=f.rowid WHERE f MATCH ? ORDER BY bm25(f) LIMIT ?", (query, limit)).fetchall()
        return tuple(row[0] for row in rows)

    def rebuild(self, connection: sqlite3.Connection, rows: list[tuple[str, str, str]]) -> int:
        if not self.available:
            return 0
        connection.execute(f"DELETE FROM {self.TABLE}")
        connection.execute(f"DELETE FROM {self.MAP_TABLE}")
        for memory_id, content, tags in rows:
            self.index(connection, memory_id, content, tags)
        return len(rows)

    def integrity_check(self, connection: sqlite3.Connection) -> None:
        if self.available:
            connection.execute(f"INSERT INTO {self.TABLE}({self.TABLE}) VALUES('integrity-check')")
