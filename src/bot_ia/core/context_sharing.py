"""Construcción segura de contexto para compartir con IA externas.

Este módulo no realiza llamadas de red. Su responsabilidad es convertir la
 evidencia ya recuperada por BOT-IA en un paquete explícito y auditable.
La biblioteca sigue siendo la fuente de verdad: el resultado se etiqueta como
contexto compartido y nunca como canon nuevo.
"""

from __future__ import annotations

from dataclasses import dataclass

from .local_workflow import LocalExecution


@dataclass(frozen=True, slots=True)
class SharedContext:
    """Paquete de contexto listo para copiar a una IA externa."""

    universe_id: str
    query: str
    source_ids: tuple[str, ...]
    source_versions: tuple[tuple[str, str], ...]
    evidence_confidence: str
    text: str


def build_shared_context(execution: LocalExecution, *, max_chars: int = 18000) -> SharedContext:
    """Genera contexto desde evidencia recuperada, sin leer archivos arbitrarios.

    Sólo se incluyen fragmentos que ya pasaron por el Bibliotecario. Se limita
    el tamaño para evitar enviar accidentalmente una biblioteca completa.
    """
    if max_chars < 1000:
        raise ValueError("max_chars must be at least 1000")

    evidence = execution.evidence
    source_ids = tuple(source.entry.metadata.source_id for source in evidence.sources)
    lines: list[str] = [
        "BOT-IA — CONTEXTO COMPARTIDO",
        "",
        "Este material fue seleccionado por BOT-IA para una consulta externa.",
        "No constituye una autorización para modificar el canon ni la biblioteca.",
        "La IA externa debe tratarlo como contexto proporcionado, no como una fuente propia.",
        "",
        f"UNIVERSO: {evidence.query.universe_id}",
        f"CONSULTA: {evidence.query.text}",
        f"CONFIANZA DE LA EVIDENCIA: {getattr(evidence.confidence, 'value', evidence.confidence)}",
        "",
        "FUENTES:",
    ]
    lines.extend(f"- {source_id}" for source_id in source_ids)
    if not source_ids:
        lines.append("- (sin fuentes coincidentes)")

    lines.append("")
    lines.append("EVIDENCIA RECUPERADA:")
    remaining = max_chars - sum(len(line) + 1 for line in lines)
    for fragment in evidence.fragments:
        if remaining <= 0:
            break
        block = (
            f"\n[{fragment.source_id} | líneas {fragment.start_line}-{fragment.end_line}]\n"
            f"{fragment.text.strip()}\n"
        )
        if len(block) > remaining:
            block = block[:remaining].rstrip() + "\n[CONTEXTO RECORTADO POR LÍMITE DE SEGURIDAD]\n"
        lines.append(block)
        remaining -= len(block)

    return SharedContext(
        universe_id=evidence.query.universe_id,
        query=evidence.query.text,
        source_ids=source_ids,
        source_versions=evidence.source_versions,
        evidence_confidence=getattr(evidence.confidence, 'value', str(evidence.confidence)),
        text="\n".join(lines).strip(),
    )
