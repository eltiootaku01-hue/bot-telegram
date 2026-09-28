# -*- coding: utf-8 -*-
"""Facade mínima del Observation Core: observar, persistir y auditar."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from .models import (
    AuditEvent,
    Confidence,
    Evidence,
    EvidenceType,
    Observation,
)
from .observers import CommandObserver, FileObserver, RepositoryObserver
from .store import EvidenceStore


class ObservationCore:
    """Capa read-only respecto del sistema observado."""

    def __init__(self, repository_root: str | Path, evidence_directory: str | Path) -> None:
        self.repository_root = Path(repository_root).expanduser().resolve()
        self.store = EvidenceStore(evidence_directory)
        self.commands = CommandObserver(self.repository_root)
        self.files = FileObserver(self.repository_root)
        self.repository = RepositoryObserver(self.repository_root, self.commands)

    def record_observation(self, observation: Observation) -> Observation:
        from .models import Evidence

        evidence = Evidence.create(
            evidence_type=EvidenceType.FILE_EVIDENCE,
            source=observation.source,
            scope=observation.scope,
            result=observation.status,
            metadata={
                "observation": observation.to_dict(),
                "task_id": observation.task_id,
            },
        )
        self.store.add(evidence)
        self.audit(
            "CREATE_EVIDENCE",
            result="OK",
            evidence_id=evidence.evidence_id,
            task_id=observation.task_id,
        )
        return observation

    def observe_repository(
        self,
        *,
        scope: str = "repository",
        task_id: str | None = None,
    ) -> dict[str, Observation | Evidence]:
        results = self.repository.observe(scope=scope, task_id=task_id)
        for value in results.values():
            if isinstance(value, Evidence):
                self.store.add(value)
        evidence_ids = [
            value.evidence_id
            for value in results.values()
            if isinstance(value, Evidence)
        ]
        self.audit(
            "OBSERVE_REPOSITORY",
            result="OK",
            task_id=task_id,
            metadata={"evidence_ids": evidence_ids},
        )
        return results

    def observe_file(
        self,
        path: str | Path,
        *,
        scope: str = "file",
        task_id: str | None = None,
    ) -> Observation:
        observation = self.files.exists(path, scope=scope, task_id=task_id)
        self.record_observation(observation)
        self.audit(
            "OBSERVE_FILE",
            result="OK",
            task_id=task_id,
            metadata={"path": str(path)},
        )
        return observation

    def hash_file(
        self,
        path: str | Path,
        *,
        scope: str = "file",
        task_id: str | None = None,
    ) -> Observation:
        observation = self.files.hash(path, scope=scope, task_id=task_id)
        self.record_observation(observation)
        self.audit(
            "VERIFY_HASH",
            result=observation.status.value,
            task_id=task_id,
            metadata={"path": str(path)},
        )
        return observation

    def run_command(
        self,
        command: Sequence[str],
        *,
        scope: str = "command",
        task_id: str | None = None,
    ) -> Evidence:
        evidence = self.commands.run(command, scope=scope, task_id=task_id)
        self.store.add(evidence)
        self.audit(
            "VERIFY_COMMAND",
            result=evidence.result.value,
            task_id=task_id,
            evidence_id=evidence.evidence_id,
        )
        return evidence

    def diff(
        self,
        *,
        scope: str = "repository",
        task_id: str | None = None,
    ) -> Evidence:
        evidence = self.repository.diff(scope=scope, task_id=task_id)
        self.store.add(evidence)
        self.audit(
            "VERIFY_DIFF",
            result=evidence.result.value,
            task_id=task_id,
            evidence_id=evidence.evidence_id,
        )
        return evidence

    def verify_command_result(
        self,
        evidence: Evidence,
        *,
        expected_exit_code: int = 0,
    ) -> bool:
        if evidence.type is not EvidenceType.TEST_EVIDENCE:
            raise ValueError("command verification requires TEST_EVIDENCE")
        matches = evidence.exit_code == expected_exit_code
        self.audit(
            "VERIFY_COMMAND_RESULT",
            result="PASS" if matches else "FAIL",
            evidence_id=evidence.evidence_id,
            metadata={
                "expected_exit_code": expected_exit_code,
                "actual_exit_code": evidence.exit_code,
            },
        )
        return matches

    def verify_file_hash(
        self,
        path: str | Path,
        expected_hash: str,
        *,
        scope: str = "file",
        task_id: str | None = None,
    ) -> bool:
        observation = self.hash_file(path, scope=scope, task_id=task_id)
        matches = (
            observation.value == expected_hash
            if observation.value is not None
            else False
        )
        self.audit(
            "VERIFY_FILE_HASH",
            result="PASS" if matches else "FAIL",
            task_id=task_id,
            metadata={
                "path": str(path),
                "expected_hash": expected_hash,
                "actual_hash": observation.value,
            },
        )
        return matches

    def update_confidence(
        self,
        evidence_id: str,
        confidence: Confidence,
    ) -> Evidence:
        evidence = self.store.update_confidence(evidence_id, confidence)
        self.audit(
            "UPDATE_CONFIDENCE",
            result=confidence.value,
            evidence_id=evidence_id,
        )
        return evidence

    def audit(
        self,
        operation: str,
        *,
        result: str,
        task_id: str | None = None,
        evidence_id: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> AuditEvent:
        event = AuditEvent.create(
            operation=operation,
            actor="supervisor.observation_core",
            result=result,
            task_id=task_id,
            evidence_id=evidence_id,
            metadata=metadata,
        )
        return self.store.add_audit(event)


__all__ = ["ObservationCore"]
