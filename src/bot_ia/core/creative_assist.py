"""Herramientas creativas deterministas: ayudan a expandir bocetos sin consumir API."""

from __future__ import annotations

import re


_STOP = {"de", "la", "el", "y", "a", "en", "un", "una", "que", "con", "por", "para", "se"}


def _clean(text: str) -> str:
    return " ".join(text.strip().split())


def expand_scene_sketch(sketch: str, *, max_questions: int = 12) -> str:
    """Convierte un boceto corto en preguntas de desarrollo, sin llamar a un LLM."""
    sketch = _clean(sketch)
    if not sketch:
        return "Necesito aunque sea unas pocas palabras del hueco de la escena para poder desarmarlo en preguntas."
    if max_questions < 1:
        raise ValueError("max_questions must be positive")

    tokens = [t for t in re.findall(r"[\wáéíóúüñÁÉÍÓÚÜÑ]+", sketch) if t.casefold() not in _STOP]
    focus = " ".join(tokens[:8]) or sketch
    questions = (
        f"1. ¿Qué ocurre exactamente en este momento de la escena ({focus})?",
        "2. ¿Dónde está Kuro y qué estaba haciendo justo antes?",
        "3. ¿Por qué Kuro decide actuar en vez de seguir caminando o marcharse?",
        "4. ¿A quién ayuda, encuentra o afecta con su acción?",
        "5. ¿Quién es esa persona y qué relación previa tiene con Kuro, si existe?",
        "6. ¿Kuro siente algo por esa persona: curiosidad, preocupación, ternura, miedo, confianza, molestia u otra cosa?",
        "7. ¿Qué peligro, problema o necesidad provoca que Kuro intervenga?",
        "8. ¿Qué hace Kuro primero, qué hace después y cuál es la consecuencia de cada acción?",
        "9. ¿Alguien presencia la escena y cambia su opinión sobre Kuro por lo que acaba de ver?",
        "10. ¿Qué pequeño detalle físico, objeto, comida, lugar o gesto puede darle personalidad a la escena?",
        "11. ¿La escena termina resolviendo el problema o deja una consecuencia que permita continuar el capítulo?",
        "12. ¿Este hueco funciona mejor como una sola escena o como varios mini-sketches encadenados?",
    )
    return "\n".join(questions[:max_questions])


def build_stuck_menu() -> tuple[tuple[tuple[str, str], ...], ...]:
    return (
        (("🧰 Usar objetos locales", "stuck:local"),),
        (("🔐 Crear algo con API", "stuck:api"),),
        (("📋 Crear pregunta para otra IA", "stuck:prompt"),),
        (("⬅️ Menú", "menu:main"),),
    )
