"""Preparación segura de contexto para una IA externa.

Este módulo NO es un puente de red y NO concede acceso a la biblioteca.
BOT-IA recupera evidencia local y este componente la convierte en un paquete
pequeño, auditable y copiable. La IA externa sólo recibe el texto que el
usuario decide copiar/pegar.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import re
import uuid

from .local_workflow import LocalExecution


_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"gsk_[A-Za-z0-9_-]{16,}"),
    re.compile(r"sk-or-v1-[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)(?:api[_-]?key|token|secret)\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{12,}"),
)


class ShareScope(str, Enum):
    """Alcance de lo que puede salir del proceso de BOT-IA."""

    RELEVANT = "relevant"


@dataclass(frozen=True, slots=True)
class SharedContext:
    """Paquete textual independiente, listo para copiar a otra IA."""

    packet_id: str
    scope: ShareScope
    universe_id: str
    query: str
    source_ids: tuple[str, ...]
    source_versions: tuple[tuple[str, str], ...]
    evidence_confidence: str
    text: str
    content_sha256: str
    redactions: int = 0


def _redact_sensitive_text(text: str) -> tuple[str, int]:
    """Oculta credenciales comunes si alguien las almacenó accidentalmente."""
    redactions = 0
    result = text
    for pattern in _SECRET_PATTERNS:
        result, count = pattern.subn("[DATO SENSIBLE OMITIDO]", result)
        redactions += count
    return result, redactions


def build_shared_context(
    execution: LocalExecution,
    *,
    max_chars: int = 18000,
    scope: ShareScope = ShareScope.RELEVANT,
) -> SharedContext:
    """Genera un paquete desde evidencia recuperada, sin leer archivos arbitrarios.

    El alcance actual es deliberadamente conservador: sólo comparte los
    fragmentos recuperados por el Bibliotecario para la consulta. No existe un
    modo implícito de compartir una biblioteca, carpeta o universo completo.
    """
    if max_chars < 1000:
        raise ValueError("max_chars must be at least 1000")

    evidence = execution.evidence
    source_ids = tuple(source.entry.metadata.source_id for source in evidence.sources)
    lines: list[str] = [
        "BOT-IA — CONTEXTO COMPARTIDO",
        "",
        "MODO: sólo evidencia relevante recuperada localmente",
        "Este paquete es una copia controlada de contexto para una IA externa.",
        "No concede acceso a BOT-IA, a la biblioteca ni al sistema local.",
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

    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return SharedContext(
        packet_id=f"ctx-{uuid.uuid4().hex[:12]}",
        scope=scope,
        universe_id=evidence.query.universe_id,
        query=evidence.query.text,
        source_ids=source_ids,
        source_versions=evidence.source_versions,
        evidence_confidence=getattr(evidence.confidence, 'value', str(evidence.confidence)),
        text=text,
        content_sha256=digest,
        redactions=redactions,
    )
