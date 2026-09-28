# -*- coding: utf-8 -*-
"""Persistencia local, simple y append-only para evidencia y auditoría."""

from __future__ import annotations

import json
from pathlib import Path
import threading
from typing import Any

from .models import AuditEvent, Confidence, Evidence, EvidenceStatus, EvidenceType


class EvidenceStore:
    """Almacena evidencia y auditoría en JSONL local, sin tocar el repositorio."""

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory).expanduser().resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self._evidence_path = self.directory / "evidence.jsonl"
        self._audit_path = self.directory / "audit.jsonl"
        self._lock = threading.RLock()

    def add(self, evidence: Evidence) -> Evidence:
        with self._lock:
            self._append(self._evidence_path, evidence.to_dict())
        return evidence

    def get(self, evidence_id: str) -> Evidence | None:
        for record in self._read(self._evidence_path):
            if record.get("evidence_id") == evidence_id:
                return self._from_dict(record)
        return None

    def list(self, *, task_id: str | None = None) -> list[Evidence]:
        records = [self._from_dict(record) for record in self._read(self._evidence_path)]
        if task_id is None:
            return records
        return [item for item in records if item.metadata.get("task_id") == task_id]

    def update_confidence(self, evidence_id: str, confidence: Confidence) -> Evidence:
        if not isinstance(confidence, Confidence):
            confidence = Confidence(str(confidence))
        with self._lock:
            records = self._read(self._evidence_path)
            found = False
            updated: dict[str, Any] | None = None
            for record in records:
                if record.get("evidence_id") == evidence_id:
                    found = True
                    current = Confidence(record["confidence"])
                    if current is Confidence.VERIFIED and confidence is not Confidence.VERIFIED:
                        raise ValueError("VERIFIED confidence cannot be silently downgraded")
                    record["confidence"] = confidence.value
                    updated = record
                    break
            if not found or updated is None:
                raise KeyError(f"unknown evidence_id: {evidence_id}")
            self._rewrite(self._evidence_path, records)
            return self._from_dict(updated)

    def add_audit(self, event: AuditEvent) -> AuditEvent:
        with self._lock:
            self._append(self._audit_path, event.to_dict())
        return event

    def list_audit(self) -> list[AuditEvent]:
        return [self._audit_from_dict(record) for record in self._read(self._audit_path)]

    @staticmethod
    def _append(path: Path, record: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    @staticmethod
    def _read(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        records: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    records.append(json.loads(line))
        return records

    @staticmethod
    def _rewrite(path: Path, records: list[dict[str, Any]]) -> None:
        temp = path.with_suffix(path.suffix + ".tmp")
        with temp.open("w", encoding="utf-8", newline="\n") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        temp.replace(path)

    @staticmethod
    def _from_dict(record: dict[str, Any]) -> Evidence:
        return Evidence(
            evidence_id=record["evidence_id"],
            type=EvidenceType(record["type"]),
            source=record["source"],
            timestamp=record["timestamp"],
            scope=record["scope"],
            result=EvidenceStatus(record["result"]),
            command=record.get("command"),
            exit_code=record.get("exit_code"),
            artifact=record.get("artifact"),
            hash=record.get("hash"),
            metadata=record.get("metadata") or {},
            confidence=Confidence(record.get("confidence", Confidence.INSPECTED.value)),
        )

    @staticmethod
    def _audit_from_dict(record: dict[str, Any]) -> AuditEvent:
        return AuditEvent(
            audit_id=record["audit_id"],
            task_id=record.get("task_id"),
            operation=record["operation"],
            actor=record["actor"],
            timestamp=record["timestamp"],
            result=record["result"],
            evidence_id=record.get("evidence_id"),
            metadata=record.get("metadata") or {},
        )
