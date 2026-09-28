# -*- coding: utf-8 -*-
"""Observadores deterministas y de solo lectura del Observation Core."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import sys
from typing import Sequence

from .models import Evidence, EvidenceStatus, EvidenceType, Observation


class CommandNotAuthorized(RuntimeError):
    """El comando solicitado no pertenece a la política read-only."""


class CommandObserver:
    """Ejecutor mínimo de comandos allowlisted, sin shell."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()

    def _authorized(self, command: Sequence[str]) -> bool:
        if not command:
            return False
        executable = Path(command[0]).name.lower()
        args = list(command[1:])
        if executable not in {"git", "git.exe"}:
            python_names = {
                Path(sys.executable).name.lower(),
                "python",
                "python3",
                "python.exe",
                "python3.exe",
            }
            return executable in python_names and args == ["--version"]
        if not args:
            return False
        subcommand = args[0]
        if subcommand == "branch":
            return args == ["branch", "--show-current"]
        if subcommand == "config":
            return args == ["config", "--get", "remote.origin.url"]
        if subcommand == "rev-parse":
            return args in (["rev-parse", "HEAD"], ["rev-parse", "--show-toplevel"])
        if subcommand == "status":
            return args == ["status", "--porcelain=v1", "--untracked-files=all"]
        if subcommand == "diff":
            allowed = {"--name-only", "--name-status", "--stat", "--no-ext-diff", "--unified=0"}
            return all(arg in allowed for arg in args[1:]) and len(args) > 1
        if subcommand == "hash-object":
            return all(arg not in {"-w", "--stdin-paths"} for arg in args[1:])
        return False

    def run(self, command: Sequence[str], *, scope: str, task_id: str | None = None) -> Evidence:
        command = tuple(str(part) for part in command)
        if not self._authorized(command):
            return Evidence.create(
                evidence_type=EvidenceType.TEST_EVIDENCE,
                source="command_observer",
                scope=scope,
                result=EvidenceStatus.BLOCKED,
                command=list(command),
                metadata={"reason": "COMMAND_NOT_AUTHORIZED", "task_id": task_id},
            )
        completed = subprocess.run(
            list(command),
            cwd=self.root,
            shell=False,
            capture_output=True,
            text=True,
            check=False,
        )
        return Evidence.create(
            evidence_type=EvidenceType.TEST_EVIDENCE,
            source="command_observer",
            scope=scope,
            result=EvidenceStatus.TESTED,
            command=list(command),
            exit_code=completed.returncode,
            metadata={
                "task_id": task_id,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "result": "PASS" if completed.returncode == 0 else "FAIL",
                "environment": {
                    "python": sys.version,
                    "os": os.name,
                },
            },
        )


class FileObserver:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()

    def _safe_path(self, path: str | Path) -> Path:
        candidate = (
            (self.root / path).resolve()
            if not Path(path).is_absolute()
            else Path(path).resolve()
        )
        if candidate != self.root and self.root not in candidate.parents:
            raise ValueError("path escapes observation root")
        return candidate

    def exists(self, path: str | Path, *, scope: str, task_id: str | None = None) -> Observation:
        target = self._safe_path(path)
        return Observation.create(
            source="file_observer",
            target=str(target),
            observation_type="FILE_EXISTS",
            value=target.exists(),
            scope=scope,
            task_id=task_id,
        )

    def hash(self, path: str | Path, *, scope: str, task_id: str | None = None) -> Observation:
        target = self._safe_path(path)
        if not target.is_file():
            return Observation.create(
                source="file_observer",
                target=str(target),
                observation_type="FILE_HASH",
                value=None,
                scope=scope,
                task_id=task_id,
                status=EvidenceStatus.UNKNOWN,
            )
        digest = hashlib.sha256()
        with target.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return Observation.create(
            source="file_observer",
            target=str(target),
            observation_type="FILE_HASH",
            value=digest.hexdigest(),
            scope=scope,
            task_id=task_id,
        )

    def metadata(self, path: str | Path, *, scope: str, task_id: str | None = None) -> Observation:
        target = self._safe_path(path)
        if not target.exists():
            value = None
            status = EvidenceStatus.UNKNOWN
        else:
            stat = target.stat()
            value = {
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "is_file": target.is_file(),
                "is_dir": target.is_dir(),
            }
            status = EvidenceStatus.OBSERVED
        return Observation.create(
            source="file_observer",
            target=str(target),
            observation_type="FILE_METADATA",
            value=value,
            scope=scope,
            task_id=task_id,
            status=status,
        )


class RepositoryObserver:
    def __init__(self, root: str | Path, commands: CommandObserver | None = None) -> None:
        self.root = Path(root).expanduser().resolve()
        self.commands = commands or CommandObserver(self.root)

    def observe(
        self,
        *,
        scope: str = "repository",
        task_id: str | None = None,
    ) -> dict[str, Observation | Evidence]:
        results: dict[str, Observation | Evidence] = {}
        commands = {
            "repository": ["git", "config", "--get", "remote.origin.url"],
            "branch": ["git", "branch", "--show-current"],
            "head": ["git", "rev-parse", "HEAD"],
            "working_tree": ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            "changed_files": ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        }
        for key, command in commands.items():
            evidence = self.commands.run(command, scope=scope, task_id=task_id)
            results[key] = evidence
            if evidence.result is EvidenceStatus.TESTED:
                raw_output = str(evidence.metadata.get("stdout", ""))
                output = raw_output.strip()
                value: object = output
                if key in {"working_tree", "changed_files"}:
                    value = self._changed_files(raw_output)
                results[f"{key}_observation"] = Observation.create(
                    source="repository_observer",
                    target=str(self.root),
                    observation_type={
                        "repository": "REPOSITORY",
                        "branch": "REPOSITORY_BRANCH",
                        "head": "REPOSITORY_HEAD",
                        "working_tree": "WORKING_TREE_STATE",
                        "changed_files": "CHANGED_FILES",
                    }[key],
                    value=value,
                    scope=scope,
                    task_id=task_id,
                )
        return results

    def diff(self, *, scope: str = "repository", task_id: str | None = None) -> Evidence:
        return self.commands.run(
            ["git", "diff", "--name-status"],
            scope=scope,
            task_id=task_id,
        )

    @staticmethod
    def _changed_files(output: str) -> list[str]:
        changed: list[str] = []
        for line in output.splitlines():
            if len(line) < 4:
                continue
            value = line[3:].strip()
            if " -> " in value:
                value = value.split(" -> ", 1)[1]
            if value:
                changed.append(value)
        return changed
