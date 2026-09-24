# -*- coding: utf-8 -*-
"""Persistencia local para proyectos/novelas creados desde BOT-IA."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
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

    def __init__(self, workspace_root: Path, *, registry_path: str = "work/projects.json", projects_dir: str = "work/projects") -> None:
        self._workspace_root = workspace_root.resolve()
        self._registry_path = (self._workspace_root / registry_path).resolve()
        self._projects_dir = (self._workspace_root / projects_dir).resolve()
        if not self._registry_path.is_relative_to(self._workspace_root) or not self._projects_dir.is_relative_to(self._workspace_root):
            raise ProjectError("project storage must remain inside the workspace")
        self._registry_path.parent.mkdir(parents=True, exist_ok=True)
        self._projects_dir.mkdir(parents=True, exist_ok=True)
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
            return self._create_novel_locked(display_name)

    def _create_novel_locked(self, display_name: str) -> ProjectRecord:
        name = " ".join(display_name.strip().split())
        if not name:
            raise ProjectError("project name cannot be empty")
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
                for child in sorted(root.rglob("*"), reverse=True):
                    if child.is_file() or child.is_symlink():
                        child.unlink()
                    elif child.is_dir():
                        child.rmdir()
                root.rmdir()
            raise

    @classmethod
    def slugify(cls, value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value.casefold())
        ascii_value = "".join(char for char in normalized if not unicodedata.combining(char))
        slug = cls._ID_RE.sub("-", ascii_value).strip("-")
        return slug or "proyecto"

    def _load(self) -> dict[str, ProjectRecord]:
        if not self._registry_path.is_file():
            return {}
        try:
            data = json.loads(self._registry_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ProjectError("project registry is invalid") from error
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

    def _write(self) -> None:
        payload = [
            {"project_id": record.project_id, "display_name": record.display_name, "root_path": str(record.root_path), "project_type": record.project_type}
            for record in self._records.values()
        ]
        temporary = self._registry_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self._registry_path)
