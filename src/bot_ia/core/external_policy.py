"""Políticas puras para separar propuestas externas del conocimiento autorizado."""

from __future__ import annotations


def external_proposal_prefix() -> str:
    """Texto estable para que una salida externa nunca parezca conocimiento propio."""
    return "Referencia externa (no incorporada al canon ni a la biblioteca):"


def wrap_external_proposal(output: str) -> str:
    """Marca una respuesta de proveedor como propuesta no autoritativa."""
    cleaned = output.strip()
    if not cleaned:
        return external_proposal_prefix()
    return f"{external_proposal_prefix()}\n\n{cleaned}"
