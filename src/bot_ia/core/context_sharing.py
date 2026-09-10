"""Construcción segura de contexto para compartir con IA externas.

Este módulo no realiza llamadas de red. Su responsabilidad es convertir la
 evidencia ya recuperada por BOT-IA en un paquete explícito y auditable.
La biblioteca sigue siendo la fuente de verdad: el resultado se etiqueta como
contexto compartido y nunca como canon nuevo.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from .local_workflow import LocalExecution


_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"gsk_[A-Za-z0-9_-]{16,}"),
    re.compile(r"sk-or-v1-[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)(?:api[_-]?key|token|secret)\\s*[:=]\\s*['\"]?[A-Za-z0-9_./+=-]{12,}"),
)


@dataclass(frozen=True, slots=True)
class SharedContext:
    """Paquete de contexto listo para copiar a una IA externa."""

    universe_id: str
    query: str
    source_ids: tuple[str, ...]
    source_versions: tuple[tuple[str, str], ...]
    evidence_confidence: str
    text: str
    redactions: int = 0


def _redact_sensitive_text(text: str) -> tuple[str, int]:
    """Oculta credenciales comunes si alguien las almacenó accidentalmente.

    La protección es deliberadamente defensiva: compartir contexto nunca debe
    convertirse en una vía para sacar secretos del entorno local. El módulo no
    intenta interpretar el valor de una credencial ni enviarlo a ningún sitio.
    """
    redactions = 0
    result = text
    for pattern in _SECRET_PATTERNS:
        result, count = pattern.subn("[DATO SENSIBLE OMITIDO]", result)
        redactions += count
    return result, redactions


def build_shared_context(execution: LocalExecution, *, max_chars: int = 18000) -> SharedContext:
    """Genera contexto desde evidencia recuperada, sin leer archivos arbitrarios.

    Sólo se incluyen fragmentos que ya pasaron por el Bibliotecario. Se limita
    el tamaño para evitar enviar accidentalmente una biblioteca completa y se
    redactan patrones de credenciales comunes como defensa adicional.
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
    header = "\n".join(lines)
    remaining = max_chars - len(header)
    redactions = 0
    if remaining > 0:
        for fragment in evidence.fragments:
            if remaining <= 0:
                break
            safe_fragment, count = _redact_sensitive_text(fragment.text.strip())
            redactions += count
            block = (
                f"\n[{fragment.source_id} | líneas {fragment.start_line}-{fragment.end_line}]\n"
                f"{safe_fragment}\n"
            )
            if len(block) <= remaining:
                lines.append(block)
                remaining -= len(block)
                continue
            marker = "\n[CONTEXTO RECORTADO POR LÍMITE DE SEGURIDAD]\n"
            lines.append((block[: max(0, remaining - len(marker))] + marker)[:remaining])
            remaining = 0
            break

    text = "\n".join(lines).strip()
    text, header_redactions = _redact_sensitive_text(text)
    redactions += header_redactions
    if len(text) > max_chars:
        text = text[:max_chars].rstrip()

    return SharedContext(
        universe_id=evidence.query.universe_id,
        query=evidence.query.text,
        source_ids=source_ids,
        source_versions=evidence.source_versions,
        evidence_confidence=getattr(evidence.confidence, 'value', str(evidence.confidence)),
        text=text,
        redactions=redactions,
    )
