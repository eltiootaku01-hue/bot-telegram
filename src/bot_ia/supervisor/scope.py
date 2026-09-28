# -*- coding: utf-8 -*-
"""Scope Lock contractualo con default deny y containment de rutas."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath
from typing import Iterable


class ScopeOperation(str, Enum):
    READ = "READ"
    WRITE = "WRITE"
    CREATE = "CREATE"
    DELETE = "DELETE"
    EXECUTE = "EXECUTE"


class ScopeStatus(str, Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


@dataclass(frozen=True, slots=True)
class ChangeBudget:
    max_files_changed: int
    max_lines_added: int
    max_lines_deleted: int
    max_commits: int
    max_repair_attempts: int

    def __post_init__(self) -> None:
        values = (
            self.max_files_changed,
            self.max_lines_added,
            self.max_lines_deleted,
            self.max_commits,
            self.max_repair_attempts,
        )
        if any(value < 0 for value in values):
            raise ValueError("change budget values cannot be negative")


@dataclass(frozen=True, slots=True)
class ScopeLock:
    scope_id: str
    task_id: str
    repository_root: Path
    allowed_paths: tuple[str, ...] = ()
    forbidden_paths: tuple[str, ...] = ()
    allowed_operations: frozenset[ScopeOperation] = frozenset()
    forbidden_operations: frozenset[ScopeOperation] = frozenset()
    scope_owner: str = ""
    authorization: str = ""
    expires_at: str | None = None
    status: ScopeStatus = ScopeStatus.ACTIVE
    change_budget: ChangeBudget = field(
        default_factory=lambda: ChangeBudget(0, 0, 0, 0, 0)
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "repository_root", self.repository_root.expanduser().resolve())
        object.__setattr__(
            self,
            "allowed_paths",
            tuple(self._normalize_pattern(item) for item in self.allowed_paths),
        )
        object.__setattr__(
            self,
            "forbidden_paths",
            tuple(self._normalize_pattern(item) for item in self.forbidden_paths),
        )
        object.__setattr__(
            self,
            "allowed_operations",
            frozenset(ScopeOperation(item) for item in self.allowed_operations),
        )
        object.__setattr__(
            self,
            "forbidden_operations",
            frozenset(ScopeOperation(item) for item in self.forbidden_operations),
        )
        if not self.task_id:
            raise ValueError("task_id is required")
        if not self.scope_id:
            raise ValueError("scope_id is required")
        if not self.scope_owner:
            raise ValueError("scope_owner is required")
        if not self.authorization:
            raise ValueError("authorization is required")

    @classmethod
    def create(
        cls,
        *,
        scope_id: str,
        task_id: str,
        repository_root: str | Path,
        allowed_paths: Iterable[str] = (),
        forbidden_paths: Iterable[str] = (),
        allowed_operations: Iterable[ScopeOperation] = (),
        forbidden_operations: Iterable[ScopeOperation] = (),
        scope_owner: str,
        authorization: str,
        expires_at: str | None = None,
        change_budget: ChangeBudget | None = None,
    ) -> "ScopeLock":
        return cls(
            scope_id=scope_id,
            task_id=task_id,
            repository_root=Path(repository_root),
            allowed_paths=tuple(allowed_paths),
            forbidden_paths=tuple(forbidden_paths),
            allowed_operations=frozenset(allowed_operations),
            forbidden_operations=frozenset(forbidden_operations),
            scope_owner=scope_owner,
            authorization=authorization,
            expires_at=expires_at,
            change_budget=change_budget or ChangeBudget(0, 0, 0, 0, 0),
        )

    def authorize(self, operation: ScopeOperation, path: str | Path) -> bool:
        if self.status is not ScopeStatus.ACTIVE or self._expired():
            return False
        operation = ScopeOperation(operation)
        if operation in self.forbidden_operations or operation not in self.allowed_operations:
            return False
        relative = self._safe_relative(path)
        if relative is None:
            return False
        if self._matches(relative, self.forbidden_paths):
            return False
        return self._matches(relative, self.allowed_paths)

    def check_change_budget(
        self,
        *,
        files_changed: int,
        lines_added: int,
        lines_deleted: int,
        commits: int,
        repair_attempts: int,
    ) -> bool:
        values = (files_changed, lines_added, lines_deleted, commits, repair_attempts)
        if any(value < 0 for value in values):
            return False
        budget = self.change_budget
        return (
            files_changed <= budget.max_files_changed
            and lines_added <= budget.max_lines_added
            and lines_deleted <= budget.max_lines_deleted
            and commits <= budget.max_commits
            and repair_attempts <= budget.max_repair_attempts
        )

    def current_status(self) -> ScopeStatus:
        if self.status is ScopeStatus.ACTIVE and self._expired():
            return ScopeStatus.EXPIRED
        return self.status

    def _expired(self) -> bool:
        if not self.expires_at:
            return False
        value = self.expires_at.replace("Z", "+00:00")
        expires = datetime.fromisoformat(value)
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) >= expires.astimezone(timezone.utc)

    def _safe_relative(self, path: str | Path) -> str | None:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.repository_root / candidate
        try:
            resolved = candidate.expanduser().resolve()
            relative = resolved.relative_to(self.repository_root)
        except (OSError, RuntimeError, ValueError):
            return None
        return PurePosixPath(relative.as_posix()).as_posix()

    @staticmethod
    def _normalize_pattern(pattern: str) -> str:
        value = pattern.replace("\\", "/").lstrip("/")
        if value == ".":
            return ""
        return PurePosixPath(value).as_posix()

    @staticmethod
    def _matches(relative: str, patterns: tuple[str, ...]) -> bool:
        if not patterns:
            return False
        for pattern in patterns:
            if pattern.endswith("/**"):
                prefix = pattern[:-3].rstrip("/")
                if relative == prefix or relative.startswith(prefix + "/"):
                    return True
            elif fnmatchcase(relative, pattern):
                return True
        return False


__all__ = ["ChangeBudget", "ScopeLock", "ScopeOperation", "ScopeStatus"]
