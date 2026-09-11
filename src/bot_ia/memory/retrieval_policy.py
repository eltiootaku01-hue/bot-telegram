"""Presupuestos deterministas para recuperación de memoria local.

Evita que una consulta demasiado amplia convierta el índice en una fuente
ilimitada de candidatos. El presupuesto es pequeño a propósito para BOT-IA:
la recuperación local debe ser barata en un equipo de 16 GB sin GPU dedicada.
"""
from __future__ import annotations

DEFAULT_CANDIDATE_BUDGET = 512
MAX_CANDIDATE_BUDGET = 4096


def candidate_budget(requested: int | None = None) -> int:
    """Return a safe bounded candidate budget."""
    if requested is None:
        return DEFAULT_CANDIDATE_BUDGET
    if requested < 1:
        raise ValueError("candidate budget must be positive")
    return min(requested, MAX_CANDIDATE_BUDGET)
