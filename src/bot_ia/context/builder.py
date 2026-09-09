"""Reduce EvidencePack a texto mínimo, priorizado y explicable."""

from __future__ import annotations

import math

from bot_ia.contracts import Confidence
from bot_ia.librarian.models import CoverageStatus, EvidencePack, SourceType
from bot_ia.memory import MemoryMatch

from .models import ContextPack, ContextSelection, TokenBudget


class ContextBuilder:
    ALGORITHM_VERSION = "context-v2"

    def build(
        self,
        evidence: EvidencePack,
        budget: TokenBudget,
        *,
        critical_rules: tuple[str, ...] = (),
        state_summary: str | None = None,
        memory_matches: tuple[MemoryMatch, ...] = (),
        future_task: bool = False,
    ) -> ContextPack:
        selections: list[ContextSelection] = []
        omissions: list[str] = list(evidence.omissions)
        used_chars = 0
        evidence_reserve = 0

        if evidence.fragments:
            evidence_reserve = max(
                len(evidence.fragments[0].text),
                0,
            )

        def add(
            kind: str,
            text: str,
            source_id: str | None,
            ordinal: int | None,
            priority: float,
            reason: str,
        ) -> bool:
            nonlocal used_chars
            estimated = math.ceil(len(text) / budget.chars_per_token)
            effective_max_chars = budget.max_chars


            if used_chars + len(text) > effective_max_chars:
                omissions.append(f"omitted_{kind}_budget")
                return False
            selections.append(
                ContextSelection(
                    kind,
                    text,
                    source_id,
                    ordinal,
                    priority,
                    reason,
                    estimated,
                )
            )
            used_chars += len(text)
            return True

        for rule in critical_rules:
            add(
                "rule",
                f"RULE: {rule}",
                None,
                None,
                100.0,
                "critical rule",
            )

        if state_summary:
            add(
                "state",
                f"STATE: {state_summary}",
                None,
                None,
                90.0,
                "active session state",
            )

        ranked_by_id = {
            item.entry.record.source_id: item
            for item in evidence.sources
        }

        seen_text: set[str] = set()

        for fragment in evidence.fragments:
            ranked = ranked_by_id.get(fragment.source_id)
            if ranked is None:
                continue

            if (
                ranked.entry.metadata.source_type
                in {SourceType.PLANNING, SourceType.OUTLINE}
                and not future_task
            ):
                omissions.append(
                    f"omitted_planning:{fragment.source_id}"
                )
                continue

            if fragment.text in seen_text:
                omissions.append(
                    f"omitted_redundant:{fragment.source_id}"
                )
                continue

            seen_text.add(fragment.text)

            evidence_text = (
                "[EVIDENCE]\n"
                f"SOURCE: {fragment.source_id}\n"
                f"STATUS: {ranked.epistemic.value}\n"
                f"CONFIDENCE: {ranked.confidence.value}\n"
                f"AUTHORITY: {ranked.entry.record.authority.value}\n"
                f"TEXT:\n{fragment.text}"
            )

            add(
                "evidence",
                evidence_text,
                fragment.source_id,
                fragment.ordinal,
                ranked.score,
                "; ".join(ranked.reasons[:4]),
            )

        for match in memory_matches:
            if match.record.universe_id != evidence.query.universe_id:
                omissions.append(
                    f"omitted_memory_universe:{match.record.memory_id}"
                )
                continue

            add(
                "memory",
                f"MEMORY (non-canon): {match.record.content}",
                f"memory:{match.record.memory_id}",
                None,
                match.relevance,
                "authorized relevant memory",
            )

        evidence_count = sum(
            item.kind == "evidence"
            for item in selections
        )

        sufficient = (
            evidence_count > 0
            and evidence.coverage.status is not CoverageStatus.NO_ENCONTRADO
        )

        excessive = any(
            item.endswith("_budget")
            for item in omissions
        )

        text = "\n\n".join(
            item.text
            for item in selections
        )

        confidence = (
            evidence.confidence
            if sufficient
            else Confidence.LOW
        )

        return ContextPack(
            evidence.query.universe_id,
            tuple(selections),
            text,
            math.ceil(len(text) / budget.chars_per_token),
            budget,
            sufficient,
            excessive,
            tuple(dict.fromkeys(omissions)),
            evidence.source_versions,
            confidence,
            self.ALGORITHM_VERSION,
        )