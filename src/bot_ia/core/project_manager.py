# -*- coding: utf-8 -*-
"""Persistencia local para proyectos/novelas creados desde BOT-IA."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import re
import threading
import unicodedata


class ProjectError(ValueError):
    """Error de validación o persistencia de proyectos."""


@dataclass(frozen=True, slots=True)
class ProjectRecord:
    project_id: str
    display_name: str
    root_path: Path
    project_type: str = "novel"


class ProjectManager:
    """Registro persistente de proyectos creados por el usuario."""

    _ID_RE = re.compile(r"[^a-z0-9]+")
    _VALID_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    _REQUIRED_DIRECTORIES = ("biblioteca", "memoria", "canon", "historial", "config")
    MAX_DISPLAY_NAME_CHARS = 200

    def __init__(self, workspace_root: Path, *, registry_path: str = "work/projects.json", projects_dir: str = "work/projects") -> None:
        self._workspace_root = workspace_root.resolve()
        self._registry_path = (self._workspace_root / registry_path).resolve()
        self._projects_dir = (self._workspace_root / projects_dir).resolve()
        if not self._registry_path.is_relative_to(self._workspace_root) or not self._projects_dir.is_relative_to(self._workspace_root):
            raise ProjectError("project storage must remain inside the workspace")
        self._registry_path.parent.mkdir(parents=True, exist_ok=True)
        self._projects_dir.mkdir(parents=True, exist_ok=True)
        self._registry_lock_path = self._registry_path.with_suffix(".json.lock")
        self._lock = threading.RLock()
        self._records = self._load()

    @property
    def registry_path(self) -> Path:
        return self._registry_path

    @property
    def projects_dir(self) -> Path:
        return self._projects_dir

    def all(self) -> tuple[ProjectRecord, ...]:
        with self._lock:
            return tuple(self._records.values())

    def get(self, project_id: str) -> ProjectRecord:
        with self._lock:
            try:
                return self._records[project_id]
            except KeyError as error:
                raise ProjectError(f"project not found: {project_id}") from error

    def create_novel(self, display_name: str) -> ProjectRecord:
        with self._lock:
            with self._process_lock():
                # Recargar después de adquirir el lock entre procesos.
                # Así dos procesos BOT-IA no pisan sus registros entre sí.
                self._records = self._load()
                return self._create_novel_locked(display_name)

    @contextmanager
    def _process_lock(self):
        handle = self._registry_lock_path.open("a+b")
        try:
            handle.seek(0)
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            try:
                if os.name == "nt":
                    import msvcrt
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()

    def _create_novel_locked(self, display_name: str) -> ProjectRecord:
        name = " ".join(display_name.strip().split())
        if not name:
            raise ProjectError("project name cannot be empty")
        if len(name) > self.MAX_DISPLAY_NAME_CHARS:
            raise ProjectError("project name is too long")
        project_id = self.slugify(name)
        if project_id in self._records:
            raise ProjectError(f"project already exists: {name}")
        root = (self._projects_dir / project_id).resolve()
        if not root.is_relative_to(self._projects_dir) or root.exists():
            raise ProjectError("project path is invalid or already exists")
        try:
            root.mkdir(parents=True, exist_ok=False)
            for directory in self._REQUIRED_DIRECTORIES:
                (root / directory).mkdir(exist_ok=False)
            record = ProjectRecord(project_id, name, root)
            self._records[project_id] = record
            try:
                self._write()
            except Exception:
                self._records.pop(project_id, None)
                raise
            return record
        except Exception:
            if root.exists() and root.is_dir():
                shutil.rmtree(root, ignore_errors=True)
            raise

    @classmethod
    def slugify(cls, value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value.casefold())
        ascii_value = "".join(char for char in normalized if not unicodedata.combining(char))
        slug = cls._ID_RE.sub("-", ascii_value).strip("-")
        return slug or "proyecto"

    def _load(self) -> dict[str, ProjectRecord]:
        primary = self._registry_path
        backup = primary.with_suffix(".json.bak")

        if not primary.is_file() and not backup.is_file():
            return {}

        try:
            if primary.is_file():
                data = json.loads(primary.read_text(encoding="utf-8"))
            else:
                data = json.loads(backup.read_text(encoding="utf-8"))
                self._restore_registry_backup(backup)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as primary_error:
            if not backup.is_file():
                raise ProjectError("project registry is invalid") from primary_error
            try:
                data = json.loads(backup.read_text(encoding="utf-8"))
                self._restore_registry_backup(backup)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as backup_error:
                raise ProjectError("project registry and backup are invalid") from backup_error
        if not isinstance(data, list):
            raise ProjectError("project registry must contain a list")
        records: dict[str, ProjectRecord] = {}
        for raw in data:
            if not isinstance(raw, dict):
                raise ProjectError("project registry contains an invalid record")
            project_id = str(raw.get("project_id", ""))
            display_name = str(raw.get("display_name", ""))
            root_raw = str(raw.get("root_path", ""))
            project_type = str(raw.get("project_type", "novel"))
            if not project_id or not display_name or not root_raw or project_type != "novel":
                raise ProjectError("project registry contains incomplete data")
            if not self._VALID_ID_RE.fullmatch(project_id) or project_id != self.slugify(display_name):
                raise ProjectError(f"project registry contains an invalid project id: {project_id}")
            if project_id in records:
                raise ProjectError(f"project registry contains a duplicate project id: {project_id}")
            root = Path(root_raw).resolve()
            if not root.is_relative_to(self._projects_dir):
                raise ProjectError("project registry path escapes projects directory")
            if root != (self._projects_dir / project_id).resolve() or not root.is_dir():
                raise ProjectError(f"project directory is missing or misplaced: {project_id}")
            missing = tuple(directory for directory in self._REQUIRED_DIRECTORIES if not (root / directory).is_dir())
            if missing:
                raise ProjectError(f"project directory is incomplete: {project_id}")
            records[project_id] = ProjectRecord(project_id, display_name, root, project_type)
        return records

    def _restore_registry_backup(self, backup: Path) -> None:
        temporary = self._registry_path.with_suffix(".json.restore.tmp")
        try:
            shutil.copy2(backup, temporary)
            with temporary.open("rb") as handle:
                os.fsync(handle.fileno())
            temporary.replace(self._registry_path)
        finally:
            temporary.unlink(missing_ok=True)

    def _safe_save_projects(self, data: list[dict[str, str]]) -> None:
        temporary = self._registry_path.with_suffix(".json.tmp")
        backup = self._registry_path.with_suffix(".json.bak")
        encoded = json.dumps(data, ensure_ascii=False, indent=2) + "\n"

        try:
            with temporary.open("w", encoding="utf-8", newline="") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())

            if self._registry_path.exists():
                shutil.copy2(self._registry_path, backup)

            temporary.replace(self._registry_path)
        finally:
            temporary.unlink(missing_ok=True)

    def _write(self) -> None:
        payload = [
            {"project_id": record.project_id, "display_name": record.display_name, "root_path": str(record.root_path), "project_type": record.project_type}
            for record in self._records.values()
        ]
        self._safe_save_projects(payload)
