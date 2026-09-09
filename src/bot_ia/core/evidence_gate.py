"""Evidence Gate determinista: la IA no puede elevar evidencia ni inventar canon."""

from __future__ import annotations

from bot_ia.librarian.models import CoverageStatus, EvidencePack


class EvidenceGate:
    """Decide qué salida factual puede llegar al usuario."""

    def build_factual_answer(
        self,
        evidence: EvidencePack,
        *,
        language: str = "es",
    ) -> str:
        status = evidence.coverage.status

        if status is CoverageStatus.NO_ENCONTRADO:
            return (
                "No encontré evidencia relevante sobre esta consulta "
                "en la documentación disponible."
            )

        if status is CoverageStatus.NO_ESTABLECIDO:
            established = [
                fragment
                for fragment in evidence.fragments
                if (
                    next(
                        (
                            ranked
                            for ranked in evidence.sources
                            if ranked.entry.record.source_id
                            == fragment.source_id
                        ),
                        None,
                    )
                    is not None
                    and next(
                        (
                            ranked
                            for ranked in evidence.sources
                            if ranked.entry.record.source_id
                            == fragment.source_id
                        )
                    ).epistemic.value
                    == "established"
                )
            ]

            if established:
                return self._format_established(established)

            return (
                "No hay información establecida sobre esta consulta. "
                "La documentación encontrada no confirma estos datos como canon."
            )

        if status is CoverageStatus.CONFLICTO:
            conflicts = ", ".join(
                conflict.conflict_key
                for conflict in evidence.conflicts
            )

            if conflicts:
                return (
                    "Encontré información en conflicto sobre esta consulta. "
                    f"Conflictos detectados: {conflicts}."
                )

            return (
                "Encontré información en conflicto sobre esta consulta. "
                "No puedo presentarla como un hecho único."
            )

        established = [
            fragment
            for fragment in evidence.fragments
            if (
                next(
                    (
                        ranked
                        for ranked in evidence.sources
                        if ranked.entry.record.source_id
                        == fragment.source_id
                    ),
                    None,
                )
                is not None
                and next(
                    (
                        ranked
                        for ranked in evidence.sources
                        if ranked.entry.record.source_id
                        == fragment.source_id
                    )
                ).epistemic.value
                == "established"
            )
        ]

        if not established:
            return (
                "La evidencia disponible no contiene información "
                "establecida suficiente para responder."
            )

        return self._format_established(established)

    @staticmethod
    def _format_established(fragments: list) -> str:
        unique: list[str] = []

        for fragment in fragments:
            text = fragment.text.strip()

            if not text or text in unique:
                continue

            unique.append(text)

        if not unique:
            return (
                "La evidencia disponible no contiene información "
                "establecida suficiente para responder."
            )

        if len(unique) == 1:
            return unique[0]

        return "\n\n".join(unique[:3])