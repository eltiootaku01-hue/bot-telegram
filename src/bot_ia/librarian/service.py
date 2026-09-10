"""Orquestación local de inventario, filtros, ranking y EvidencePack."""

from __future__ import annotations

from collections import defaultdict

from bot_ia.contracts import AuthorityLevel, Confidence, EpistemicStatus, EvidenceStatus
from bot_ia.policy import evaluate_authority

from .models import CatalogEntry, Coverage, CoverageStatus, EvidenceConflict, EvidencePack, RankedSource, RetrievalQuery, SourceType
from .retrieval import extract_fragments, is_allowed, query_terms


class LocalLibrarian:
    def retrieve(self, query: RetrievalQuery, entries: tuple[CatalogEntry, ...]) -> EvidencePack:
        scoped = tuple(entry for entry in entries if entry.record.universe_id == query.universe_id)
        allowed = tuple(entry for entry in scoped if is_allowed(entry, query))
        matched: list[tuple[CatalogEntry, tuple]] = []
        for entry in allowed:
            fragments = extract_fragments(entry, query)
            if fragments:
                matched.append((entry, fragments))

        preferred = set(query.preferred_source_ids)
        ranked = tuple(sorted(
            (self._rank(entry, fragments, max(fragment.lexical_score for fragment in fragments), query, preferred=entry.record.source_id in preferred)
             for entry, fragments in matched),
            key=lambda item: (-item.score, item.entry.record.source_id),
        ))

        fragment_candidates: list[tuple[float, int, object]] = []
        query_term_set = set(query_terms(query.text))
        for entry, source_fragments in matched:
            preferred_source = entry.record.source_id in preferred
            source_rank = next((item for item in ranked if item.entry.record.source_id == entry.record.source_id), None)
            source_bonus = source_rank.score * 0.05 if source_rank is not None else 0.0
            preferred_bonus = 0.10 if preferred_source else 0.0
            for fragment in source_fragments:
                section_bonus = self._section_score(fragment.section)
                heading_bonus = 0.0
                first_line = fragment.text.splitlines()[0].strip()
                if first_line.startswith("### ") and query_term_set:
                    heading_terms = set(query_terms(first_line[4:].strip()))
                    if query_term_set.issubset(heading_terms):
                        heading_bonus = 0.50
                fragment_score = round(fragment.lexical_score + source_bonus + preferred_bonus + section_bonus + heading_bonus, 4)
                fragment_candidates.append((fragment_score, -fragment.start_line, fragment))

        fragment_candidates.sort(key=lambda item: (-item[0], item[1], item[2].source_id, item[2].ordinal))
        fragments = tuple(item[2] for item in fragment_candidates[:query.max_fragments])
        conflicts = self._conflicts(tuple(item.entry for item in ranked))
        coverage = self._coverage(len(scoped), len(allowed), len(matched), conflicts, ranked)
        confidence = Confidence.LOW if conflicts or coverage.status is not CoverageStatus.ESTABLISHED else ranked[0].confidence
        omissions = self._omissions(coverage, len(scoped), len(allowed))
        versions = tuple((item.entry.record.source_id, item.entry.version) for item in ranked)
        explanation = tuple(reason for item in ranked for reason in item.reasons)
        return EvidencePack(query, ranked, fragments, explanation, conflicts, omissions, confidence, versions, coverage)

    @staticmethod
    def _section_score(section: str) -> float:
        normalized = section.casefold().strip()
        if normalized in {"hechos confirmados en manuscrito", "hechos mostrados"}:
            return 0.40
        if normalized in {"pendiente", "pendiente de decidir", "estado de planificación", "estado de planificacion"}:
            return -0.20
        return 0.0

    @staticmethod
    def _section_epistemic(section: str) -> tuple[EvidenceStatus, EpistemicStatus, Confidence]:
        normalized = section.casefold().strip()
        if normalized in {"hechos confirmados en manuscrito", "hechos mostrados"}:
            return EvidenceStatus.FOUND, EpistemicStatus.ESTABLISHED, Confidence.HIGH
        if normalized in {"pendiente", "pendiente de decidir", "estado de planificación", "estado de planificacion"}:
            return EvidenceStatus.FOUND, EpistemicStatus.NOT_ESTABLISHED, Confidence.MEDIUM
        return EvidenceStatus.UNVERIFIED, EpistemicStatus.NOT_ESTABLISHED, Confidence.LOW

    def _rank(self, entry: CatalogEntry, fragments: tuple, relevance: float, query: RetrievalQuery, *, preferred: bool = False) -> RankedSource:
        base_decision = evaluate_authority(entry.record)
        section_decisions = [self._section_epistemic(fragment.section) for fragment in fragments]
        established = [decision for decision in section_decisions if decision[1] is EpistemicStatus.ESTABLISHED]
        if established:
            evidence, epistemic, confidence = EvidenceStatus.FOUND, EpistemicStatus.ESTABLISHED, Confidence.HIGH
        else:
            section_found = [decision for decision in section_decisions if decision[0] is EvidenceStatus.FOUND]
            if section_found:
                evidence, epistemic, confidence = EvidenceStatus.FOUND, EpistemicStatus.NOT_ESTABLISHED, Confidence.MEDIUM
            else:
                evidence, epistemic, confidence = base_decision.evidence, base_decision.epistemic, base_decision.confidence

        authority_weight = {
            AuthorityLevel.PRIMARY: 0.30,
            AuthorityLevel.INTERNAL_CANON: 0.25,
            AuthorityLevel.AUTHORIAL_DECISION: 0.22,
            AuthorityLevel.EXTERNAL_REFERENCE: 0.10,
            AuthorityLevel.PLAN: 0.08,
            AuthorityLevel.UNKNOWN: 0.02,
        }[entry.record.authority]
        evidence_weight = 0.20 if evidence is EvidenceStatus.FOUND else 0.03
        epistemic_weight = 0.15 if epistemic is EpistemicStatus.ESTABLISHED else 0.02
        preferred_bonus = 0.25 if preferred else 0.0
        identity_bonus = 0.0
        normalized_query = query_terms(query.text)
        is_identity_query = len(normalized_query) == 1 and normalized_query[0] not in {"arco", "saga"}
        if is_identity_query and entry.metadata.source_type is SourceType.CHARACTER:
            for fragment in fragments:
                first_line = fragment.text.splitlines()[0].strip()
                if not first_line.startswith("### "):
                    continue
                heading_terms = set(query_terms(first_line[4:].strip()))
                if normalized_query[0] in heading_terms and fragment.lexical_score >= 1.0:
                    identity_bonus = 0.30
                    break

        score = round(relevance * 0.35 + authority_weight + evidence_weight + epistemic_weight + preferred_bonus + identity_bonus, 4)
        reasons = (f"relevance={relevance:.2f}", f"authority={entry.record.authority.value}", f"evidence={evidence.value}", f"epistemic={epistemic.value}", f"preferred_source={preferred}", f"version={entry.version[:12]}")
        return RankedSource(entry, score, relevance, evidence, epistemic, confidence, reasons)

    @staticmethod
    def _conflicts(entries: tuple[CatalogEntry, ...]) -> tuple[EvidenceConflict, ...]:
        groups: dict[str, list[CatalogEntry]] = defaultdict(list)
        for entry in entries:
            if entry.metadata.conflict_key:
                groups[entry.metadata.conflict_key].append(entry)
        conflicts = []
        for key, group in sorted(groups.items()):
            if len(group) > 1 and len({item.version for item in group}) > 1:
                conflicts.append(EvidenceConflict(key, tuple(sorted(item.record.source_id for item in group)), "multiple incompatible versions share conflict key"))
        return tuple(conflicts)

    @staticmethod
    def _coverage(scoped_count: int, allowed_count: int, matched_count: int, conflicts: tuple[EvidenceConflict, ...], ranked: tuple[RankedSource, ...]) -> Coverage:
        if conflicts:
            status = CoverageStatus.CONFLICTO
        elif not matched_count:
            status = CoverageStatus.NO_ENCONTRADO
        elif not any(item.epistemic is EpistemicStatus.ESTABLISHED for item in ranked):
            status = CoverageStatus.NO_ESTABLECIDO
        else:
            status = CoverageStatus.ESTABLISHED
        return Coverage(status, scoped_count, matched_count, scoped_count - allowed_count)

    @staticmethod
    def _omissions(coverage: Coverage, scoped_count: int, allowed_count: int) -> tuple[str, ...]:
        if coverage.status is CoverageStatus.NO_ENCONTRADO:
            return ("NO_ENCONTRADO",)
        if coverage.status is CoverageStatus.NO_ESTABLECIDO:
            return ("NO_ESTABLECIDO",)
        if coverage.status is CoverageStatus.CONFLICTO:
            return ("CONFLICTO",)
        if scoped_count != allowed_count:
            return ("sources excluded by temporal or spoiler filters",)
        return ()
