# -*- coding: utf-8 -*-
"""SQLite local para memoria controlada; no carga la base completa."""
from __future__ import annotations

from contextlib import closing, contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
import threading
import time
from uuid import uuid4

from bot_ia.change_management import ChangeManager
from bot_ia.contracts import Confidence, UniverseRegistry

from .fts import MemoryFTS
from .models import MemoryMatch, MemoryStatus, MemoryType, PersistentMemoryRecord
from .retrieval_policy import candidate_budget

_TOKENS = re.compile(r"[\wáéíóúüñ]+", re.IGNORECASE)
_SECRET = re.compile(r"(?:sk-[A-Za-z0-9_-]{12,}|AIza[A-Za-z0-9_-]{12,}|\d{8,12}:[A-Za-z0-9_-]{20,})")
_CONFIDENCE_RANK = {Confidence.HIGH: 3, Confidence.MEDIUM: 2, Confidence.LOW: 1, Confidence.NONE: 0}
MAX_MEMORY_CONTENT_CHARS = 50_000
MAX_MEMORY_FIELD_CHARS = 2_048
MAX_MEMORY_TAGS = 64
MAX_MEMORY_TAG_CHARS = 128
MAX_MEMORY_QUERY_CHARS = 24_000
EXPIRY_SWEEP_INTERVAL_SECONDS = 30.0


class MemoryStorageError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _contains_secret(*values: object) -> bool:
    return any(_SECRET.search(str(value)) for value in values if value is not None)


class MemoryStore:
    SCHEMA_VERSION = 1
    APPLICATION_ID = 0x4249414D  # "BIAM"

    def __init__(self, workspace_root: Path, registry: UniverseRegistry, database_path: str = "work/bot_ia_memory.sqlite3") -> None:
        self._registry = registry
        self._path = ChangeManager(workspace_root).resolve_target(database_path)
        self._closed = False
        self._fts_available = False
        self._lock = threading.RLock()
        self._last_expiry_sweep = 0.0
        self._initialize()

    @property
    def path(self) -> Path:
        return self._path

    def close(self) -> None:
        self._closed = True

    def _connection(self) -> sqlite3.Connection:
        if self._closed:
            raise MemoryStorageError("memory store is closed")
        connection = sqlite3.connect(self._path, timeout=10.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    @contextmanager
    def _transaction(self):
        connection = self._connection()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._path, timeout=10.0)
        try:
            connection.execute("PRAGMA busy_timeout=10000")
            connection.execute("PRAGMA journal_mode=WAL")
            application_id = connection.execute("PRAGMA application_id").fetchone()[0]
            if application_id not in (0, self.APPLICATION_ID):
                raise MemoryStorageError("database belongs to another application")
            connection.execute(f"PRAGMA application_id={self.APPLICATION_ID}")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version > self.SCHEMA_VERSION:
                raise MemoryStorageError("memory database is newer than this BOT-IA version")
            if version == 0:
                connection.execute("CREATE TABLE IF NOT EXISTS memories (memory_id TEXT PRIMARY KEY, universe_id TEXT NOT NULL, user_id TEXT NOT NULL, conversation_id TEXT, memory_type TEXT NOT NULL, content TEXT NOT NULL, source TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, approved INTEGER NOT NULL, status TEXT NOT NULL, confidence TEXT NOT NULL, expires_at TEXT, revoked_at TEXT, tags TEXT NOT NULL, related_entities TEXT NOT NULL, provenance TEXT NOT NULL, supersedes TEXT, conflicts_with TEXT NOT NULL)")
                connection.execute("CREATE INDEX IF NOT EXISTS memory_lookup ON memories(universe_id, user_id, status, approved, expires_at)")
                connection.execute(f"PRAGMA user_version={self.SCHEMA_VERSION}")
            self._fts_available = MemoryFTS.ensure(connection)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def propose(self, *, universe_id: str, user_id: str, conversation_id: str | None, memory_type: MemoryType, content: str, source: str, provenance: str, confidence: Confidence = Confidence.MEDIUM, expires_at: datetime | None = None, tags: tuple[str, ...] = (), related_entities: tuple[str, ...] = ()) -> PersistentMemoryRecord:
        if not self._registry.contains(universe_id):
            raise MemoryStorageError("memory universe is not registered")
        if (
            not user_id
            or not content.strip()
            or not source
            or not provenance
        ):
            raise MemoryStorageError("memory contains invalid content")
        if (
            len(user_id) > MAX_MEMORY_FIELD_CHARS
            or (conversation_id is not None and len(conversation_id) > MAX_MEMORY_FIELD_CHARS)
            or len(content) > MAX_MEMORY_CONTENT_CHARS
            or len(source) > MAX_MEMORY_FIELD_CHARS
            or len(provenance) > MAX_MEMORY_FIELD_CHARS
            or len(tags) > MAX_MEMORY_TAGS
            or len(related_entities) > MAX_MEMORY_TAGS
            or any(len(tag) > MAX_MEMORY_TAG_CHARS for tag in tags)
            or any(len(entity) > MAX_MEMORY_TAG_CHARS for entity in related_entities)
        ):
            raise MemoryStorageError("memory fields exceed safety limits")
        if _contains_secret(user_id, conversation_id, content, source, provenance, tags, related_entities):
            raise MemoryStorageError("memory contains sensitive content")
        now = _now()
        record = PersistentMemoryRecord(str(uuid4()), universe_id, user_id, conversation_id, memory_type, content.strip(), source, now, now, False, MemoryStatus.PROPOSED, confidence, expires_at, None, tuple(tags), tuple(related_entities), provenance)
        self._insert(record)
        return record

    def _insert(self, record: PersistentMemoryRecord) -> None:
        if _contains_secret(record.user_id, record.conversation_id, record.content, record.source, record.provenance, record.tags, record.related_entities):
            raise MemoryStorageError("memory contains sensitive content")
        with self._transaction() as connection:
            try:
                connection.execute("INSERT INTO memories VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", self._values(record))
            except sqlite3.IntegrityError as error:
                raise MemoryStorageError("duplicate memory id") from error

    @staticmethod
    def _values(record: PersistentMemoryRecord) -> tuple[object, ...]:
        return (record.memory_id, record.universe_id, record.user_id, record.conversation_id, record.memory_type.value, record.content, record.source, record.created_at.isoformat(), record.updated_at.isoformat(), int(record.approved_by_author), record.status.value, record.confidence.value, record.expires_at.isoformat() if record.expires_at else None, record.revoked_at.isoformat() if record.revoked_at else None, json.dumps(record.tags), json.dumps(record.related_entities), record.provenance, record.supersedes, json.dumps(record.conflicts_with))

    def get(self, memory_id: str) -> PersistentMemoryRecord:
        with self._transaction() as connection:
            row = connection.execute("SELECT * FROM memories WHERE memory_id=?", (memory_id,)).fetchone()
        if row is None:
            raise MemoryStorageError("memory not found")
        return self._record(row)

    def approve(self, memory_id: str, *, approved_by_author: str) -> PersistentMemoryRecord:
        if not approved_by_author.strip():
            raise MemoryStorageError("explicit approver is required")
        if _contains_secret(approved_by_author):
            raise MemoryStorageError("approver contains sensitive content")
        record = self.get(memory_id)
        if record.status is not MemoryStatus.PROPOSED:
            raise MemoryStorageError("only proposed memory can be approved")
        return self._update(record, approved=True, status=MemoryStatus.ACTIVE, provenance=f"{record.provenance}; approved_by:{approved_by_author}")

    def revoke(self, memory_id: str) -> PersistentMemoryRecord:
        return self._update(self.get(memory_id), status=MemoryStatus.REVOKED, revoked_at=_now())

    def archive(self, memory_id: str) -> PersistentMemoryRecord:
        return self._update(self.get(memory_id), status=MemoryStatus.ARCHIVED)

    def record_conflict(self, memory_id: str, source_id: str) -> PersistentMemoryRecord:
        if not source_id:
            raise MemoryStorageError("conflicting source id is required")
        if _contains_secret(source_id):
            raise MemoryStorageError("conflicting source id contains sensitive content")
        record = self.get(memory_id)
        return self._update(record, status=MemoryStatus.CONFLICT, conflicts=tuple(dict.fromkeys((*record.conflicts_with, source_id))))

    def supersede(self, old_memory_id: str, replacement_memory_id: str) -> PersistentMemoryRecord:
        old, replacement = self.get(old_memory_id), self.get(replacement_memory_id)
        if old.universe_id != replacement.universe_id or old.user_id != replacement.user_id or replacement.status is not MemoryStatus.ACTIVE:
            raise MemoryStorageError("replacement must be active and share memory scope")
        with self._transaction() as connection:
            now = _now().isoformat()
            archived = connection.execute("UPDATE memories SET status=?, updated_at=? WHERE memory_id=? AND status=?", (MemoryStatus.ARCHIVED.value, now, old.memory_id, MemoryStatus.ACTIVE.value))
            linked = connection.execute("UPDATE memories SET supersedes=?, updated_at=? WHERE memory_id=? AND status=?", (old.memory_id, now, replacement.memory_id, MemoryStatus.ACTIVE.value))
            if archived.rowcount != 1 or linked.rowcount != 1:
                raise MemoryStorageError("memory supersession was not applied atomically")
        return self.get(replacement.memory_id)

    def expire_due(self, now: datetime | None = None) -> int:
        now = now or _now()
        with self._transaction() as connection:
            cursor = connection.execute("UPDATE memories SET status=?, updated_at=? WHERE status=? AND expires_at IS NOT NULL AND expires_at<=?", (MemoryStatus.EXPIRED.value, now.isoformat(), MemoryStatus.ACTIVE.value, now.isoformat()))
        return cursor.rowcount

    def retrieve(self, *, universe_id: str, user_id: str, conversation_id: str | None, query: str, now: datetime | None = None, limit: int = 5) -> tuple[MemoryMatch, ...]:
        if not self._registry.contains(universe_id) or not user_id or limit < 1:
            raise MemoryStorageError("invalid memory retrieval scope")
        now = now or _now()
        monotonic_now = time.monotonic()
        if monotonic_now - self._last_expiry_sweep >= EXPIRY_SWEEP_INTERVAL_SECONDS:
            with self._lock:
                if monotonic_now - self._last_expiry_sweep >= EXPIRY_SWEEP_INTERVAL_SECONDS:
                    self.expire_due(now)
                    self._last_expiry_sweep = monotonic_now
        if len(query) > MAX_MEMORY_QUERY_CHARS:
            query = query[:MAX_MEMORY_QUERY_CHARS]
        terms = tuple(dict.fromkeys(_TOKENS.findall(query.casefold())))[:64]
        if not terms:
            return ()
        with closing(self._connection()) as connection:
            if self._fts_available:
                try:
                    candidate_ids = MemoryFTS.query(connection, universe_id=universe_id, user_id=user_id, conversation_id=conversation_id, terms=terms)
                except sqlite3.OperationalError:
                    MemoryFTS.rebuild(connection)
                    candidate_ids = MemoryFTS.query(connection, universe_id=universe_id, user_id=user_id, conversation_id=conversation_id, terms=terms)
                if not candidate_ids:
                    rows = []
                else:
                    placeholders = ",".join("?" for _ in candidate_ids)
                    parameters: list[object] = [universe_id, user_id, MemoryStatus.ACTIVE.value, now.isoformat(), conversation_id, *candidate_ids]
                    rows = connection.execute(
                        f"SELECT * FROM memories WHERE universe_id=? AND user_id=? AND status=? AND approved=1 "
                        f"AND (expires_at IS NULL OR expires_at>?) AND (conversation_id IS NULL OR conversation_id=?) "
                        f"AND memory_id IN ({placeholders})",
                        tuple(parameters),
                    ).fetchall()
            else:
                clauses = []
                parameters = [universe_id, user_id, MemoryStatus.ACTIVE.value, now.isoformat(), conversation_id]
                for term in terms:
                    pattern = f"%{term}%"
                    clauses.append("(content LIKE ? OR tags LIKE ?)")
                    parameters.extend((pattern, pattern))
                candidate_filter = " OR ".join(clauses)
                sql = f"SELECT * FROM memories WHERE universe_id=? AND user_id=? AND status=? AND approved=1 AND (expires_at IS NULL OR expires_at>?) AND (conversation_id IS NULL OR conversation_id=?) AND ({candidate_filter}) LIMIT ?"
                rows = connection.execute(sql, tuple((*parameters, candidate_budget()))).fetchall()
        matches = []
        term_set = set(terms)
        for row in rows:
            record = self._record(row)
            words = set(_TOKENS.findall((record.content + " " + " ".join(record.tags)).casefold()))
            overlap = len(term_set & words)
            if overlap:
                matches.append(MemoryMatch(record, overlap / len(term_set)))
        return tuple(sorted(matches, key=lambda item: (-item.relevance, -_CONFIDENCE_RANK[item.record.confidence], -item.record.created_at.timestamp()))[:limit])

    def _update(self, record: PersistentMemoryRecord, *, approved: bool | None = None, status: MemoryStatus | None = None, revoked_at: datetime | None = None, provenance: str | None = None, supersedes: str | None = None, conflicts: tuple[str, ...] | None = None) -> PersistentMemoryRecord:
        updated = PersistentMemoryRecord(record.memory_id, record.universe_id, record.user_id, record.conversation_id, record.memory_type, record.content, record.source, record.created_at, _now(), record.approved_by_author if approved is None else approved, record.status if status is None else status, record.confidence, record.expires_at, record.revoked_at if revoked_at is None else revoked_at, record.tags, record.related_entities, record.provenance if provenance is None else provenance, record.supersedes if supersedes is None else supersedes, record.conflicts_with if conflicts is None else conflicts)
        if _contains_secret(updated.user_id, updated.conversation_id, updated.content, updated.source, updated.provenance, updated.tags, updated.related_entities):
            raise MemoryStorageError("memory contains sensitive content")
        with self._transaction() as connection:
            cursor = connection.execute(
                "UPDATE memories SET universe_id=?, user_id=?, conversation_id=?, memory_type=?, content=?, source=?, created_at=?, updated_at=?, approved=?, status=?, confidence=?, expires_at=?, revoked_at=?, tags=?, related_entities=?, provenance=?, supersedes=?, conflicts_with=? "
                "WHERE memory_id=? AND updated_at=?",
                (*self._values(updated)[1:], updated.memory_id, record.updated_at.isoformat()),
            )
            if cursor.rowcount != 1:
                raise MemoryStorageError("memory update did not affect exactly one record")
        return updated

    @staticmethod
    def _record(row: sqlite3.Row) -> PersistentMemoryRecord:
        try:
            created_at = datetime.fromisoformat(row["created_at"])
            updated_at = datetime.fromisoformat(row["updated_at"])
            expires_at = datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None
            revoked_at = datetime.fromisoformat(row["revoked_at"]) if row["revoked_at"] else None
            for value in (created_at, updated_at, expires_at, revoked_at):
                if value is not None and value.tzinfo is None:
                    raise ValueError("memory timestamps must be timezone-aware")

            tags = json.loads(row["tags"])
            related_entities = json.loads(row["related_entities"])
            conflicts_with = json.loads(row["conflicts_with"])
            if not all(isinstance(value, list) for value in (tags, related_entities, conflicts_with)):
                raise ValueError("memory collection fields must be JSON lists")
            if not all(isinstance(value, str) for value in (*tags, *related_entities, *conflicts_with)):
                raise ValueError("memory collection items must be strings")

            return PersistentMemoryRecord(
                row["memory_id"],
                row["universe_id"],
                row["user_id"],
                row["conversation_id"],
                MemoryType(row["memory_type"]),
                row["content"],
                row["source"],
                created_at,
                updated_at,
                bool(row["approved"]),
                MemoryStatus(row["status"]),
                Confidence(row["confidence"]),
                expires_at,
                revoked_at,
                tuple(tags),
                tuple(related_entities),
                row["provenance"],
                row["supersedes"],
                tuple(conflicts_with),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise MemoryStorageError("invalid memory record on disk") from error
