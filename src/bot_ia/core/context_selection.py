"""Selección explícita de evidencia antes de compartir contexto.

La selección opera únicamente sobre la evidencia que ya recuperó BOT-IA.
Nunca descubre archivos nuevos, nunca mezcla universos y nunca hace red.
"""

from __future__ import annotations

from dataclasses import replace

from .local_workflow import LocalExecution


def available_context_sources(execution: LocalExecution) -> tuple[str, ...]:
    """Devuelve las fuentes recuperadas que pueden aparecer en un paquete."""
    return tuple(source.entry.metadata.source_id for source in execution.evidence.sources)


def select_context_sources(
    execution: LocalExecution,
    source_ids: tuple[str, ...] | list[str],
) -> LocalExecution:
    """Crea una ejecución derivada que sólo contiene fuentes explícitamente elegidas.

    Las fuentes deben pertenecer a la evidencia recuperada para esa consulta y
    al mismo universo. Una fuente desconocida se rechaza en vez de buscarla
    silenciosamente en la biblioteca.
    """
    requested = tuple(dict.fromkeys(source_ids))
    if not requested:
        raise ValueError("at least one context source must be selected")

    available = set(available_context_sources(execution))
    unknown = tuple(source_id for source_id in requested if source_id not in available)
    if unknown:
        raise ValueError(f"context source was not retrieved for this execution: {unknown[0]}")

    selected_sources = tuple(
        source for source in execution.evidence.sources
        if source.entry.metadata.source_id in requested
    )
    selected_fragments = tuple(
        fragment for fragment in execution.evidence.fragments
        if fragment.source_id in requested
    )
    selected_versions = tuple(
        item for item in execution.evidence.source_versions
        if item[0] in requested
    )

    evidence = replace(
        execution.evidence,
        sources=selected_sources,
        fragments=selected_fragments,
        source_versions=selected_versions,
    )
    return replace(execution, evidence=evidence)
