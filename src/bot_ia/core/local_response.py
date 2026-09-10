"""Respuestas conversacionales deterministas para tareas que no necesitan un LLM."""

from __future__ import annotations

from collections.abc import Sequence

from .models import Intent


def build_local_response(
    intent: Intent,
    message: str,
    universe_name: str | None = None,
    source_names: Sequence[str] = (),
) -> str | None:
    """Devuelve una respuesta útil sin consumir un proveedor remoto."""
    text = " ".join(message.casefold().split())

    if intent is Intent.GREETING:
        if "cómo estás" in text or "como estas" in text or "qué tal" in text or "que tal" in text:
            return "¡Todo bien por aquí! Lista para trabajar contigo. ¿Qué hacemos?"
        return "¡Hola! Soy IA-chan. Estoy lista para ayudarte. ¿Qué quieres hacer?"

    if intent is Intent.HELP:
        return (
            "Puedo ayudarte a consultar la biblioteca, comprobar continuidad y canon, "
            "organizar información, revisar textos, desarrollar ideas y escribir. "
            "Primero intento resolver localmente lo que no necesita una API."
        )

    if intent is Intent.KNOWLEDGE_OVERVIEW:
        if not source_names:
            return "La biblioteca está disponible, pero ahora mismo no encontré documentos indexados."
        names = list(source_names)
        preview = ", ".join(names[:8])
        suffix = f" y {len(names) - 8} más" if len(names) > 8 else ""
        scope = f" del universo «{universe_name}»" if universe_name else ""
        return (
            f"Sí. Tengo {len(names)} documento(s) disponible(s){scope}. "
            f"Entre ellos están: {preview}{suffix}. "
            "Si quieres, puedo buscar dentro de ellos y separar canon, planificación e investigación."
        )

    if intent is Intent.ORGANIZATION:
        return "Puedo organizarlo sin llamar a una API: primero reviso la estructura, detecto duplicados y separo contenido por función antes de mover nada."

    if intent is Intent.UNIVERSE_CHANGE and universe_name:
        return f"Perfecto. Trabajaremos dentro de «{universe_name}»."

    return None
