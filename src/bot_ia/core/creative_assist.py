"""Herramientas creativas deterministas para desarrollar escenas sin API."""

from __future__ import annotations

import re

_STOP = {"de", "la", "el", "y", "a", "en", "un", "una", "que", "con", "por", "para", "se", "su", "al"}


def _clean(text: str) -> str:
    return " ".join(text.strip().split())


def expand_scene_sketch(sketch: str, *, max_questions: int = 20) -> str:
    """Convierte un boceto breve en preguntas de desarrollo, sin llamar a un LLM."""
    sketch = _clean(sketch)
    if not sketch:
        return "Necesito aunque sea unas pocas palabras del hueco de la escena para poder desarmarlo en preguntas."
    if max_questions < 1:
        raise ValueError("max_questions must be positive")
    tokens = [t for t in re.findall(r"[\wáéíóúüñÁÉÍÓÚÜÑ]+", sketch) if t.casefold() not in _STOP]
    focus = " ".join(tokens[:10]) or sketch
    questions = (
        f"1. ¿Qué ocurre exactamente en este momento ({focus})?",
        "2. ¿Dónde está Kuro y qué estaba haciendo justo antes?",
        "3. ¿Qué acaba de ocurrir que rompe la normalidad?",
        "4. ¿A quién ayuda o salva Kuro, y qué sabemos de esa persona?",
        "5. ¿Quién es esa persona y qué sabemos de ella?",
        "6. ¿Por qué Kuro decide intervenir en lugar de continuar caminando?",
        "7. ¿Kuro actúa por instinto, curiosidad, miedo, empatía, hambre, obligación u otro motivo?",
        "8. ¿Kuro tiene algún sentimiento previo hacia esa persona?",
        "9. ¿La persona reconoce a Kuro, le teme, confía en ella o no sabe quién es?",
        "10. ¿Qué peligro concreto existe si Kuro no interviene?",
        "11. ¿Qué hace Kuro primero?",
        "12. ¿Qué hace inmediatamente después?",
        "13. ¿Qué reacción provoca cada una de esas acciones?",
        "14. ¿Hay alguien observando la escena y cómo interpreta lo que ve?",
        "15. ¿Qué diálogo, pensamiento o gesto puede revelar la personalidad de Kuro?",
        "16. ¿Hay algún objeto, comida, lugar o detalle cotidiano que pueda darle identidad a la escena?",
        "17. ¿Kuro intenta quedarse para ayudar o busca marcharse cuanto antes? ¿Por qué?",
        "18. ¿Qué consecuencia deja el rescate para Kuro, para la persona salvada o para el capítulo?",
        "19. ¿El hueco funciona mejor como una escena completa o como varios mini-sketches de acciones encadenadas?",
        "20. ¿La escena termina aquí o qué debería quedar preparado al final para enlazar naturalmente con la siguiente escena?",
    )
    return "\n".join(questions[:max_questions])


def build_stuck_menu() -> tuple[tuple[tuple[str, str], ...], ...]:
    return (
        (("🧰 Usar biblioteca local", "stuck:local"),),
        (("🔐 Crear con API", "stuck:api"),),
        (("📋 Pregunta para otra IA", "stuck:prompt"),),
        (("⬅️ Menú", "menu:main"),),
    )
