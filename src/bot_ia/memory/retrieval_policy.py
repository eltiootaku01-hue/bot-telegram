# -*- coding: utf-8 -*-
"""Presupuestos deterministas para recuperación de memoria local."""
from __future__ import annotations

DEFAULT_CANDIDATE_BUDGET = 512
MAX_CANDIDATE_BUDGET = 4096


def candidate_budget(requested: int | None = None) -> int:
    """Return a safe bounded candidate budget for local retrieval."""
    if requested is None:
        return DEFAULT_CANDIDATE_BUDGET
    if requested < 1:
        raise ValueError("candidate budget must be positive")
    return min(requested, MAX_CANDIDATE_BUDGET)
