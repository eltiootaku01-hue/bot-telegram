# -*- coding: utf-8 -*-
"""Tutoriales locales del Café Otaku y matriz elemental de Waifumon."""

from __future__ import annotations

ELEMENTS = ("Fuego", "Aire", "Tierra", "Agua")
ADVANTAGES = {
    "Fuego": "Aire",
    "Aire": "Tierra",
    "Tierra": "Agua",
    "Agua": "Fuego",
}


def build_tutorial_text() -> str:
    """Explicación compacta para /tutorial y superficies sin HTML."""
    lines = [
        "📚 TUTORIAL TCG / WAIFUMON",
        "",
        "🔺 Matriz elemental:",
        "Fuego → Aire → Tierra → Agua → Fuego",
        "",
        "Cada elemento tiene ventaja sobre el siguiente de la cadena.",
        "Ejemplo: Fuego tiene ventaja sobre Aire; Agua tiene ventaja sobre Fuego.",
        "",
        "🃏 Partes de una carta:",
        "1. Marco / rareza: R, SR o UR.",
        "2. Arte: personaje centrado y completo.",
        "3. Elemento: Fuego, Agua, Tierra, Aire, Luz, Oscuridad o Neutro.",
        "4. Identidad: nombre y referencia de personaje.",
        "5. Datos Waifumon: HP, Ataque y Tipo.",
        "6. Cosplay / pose: variante visual de la carta.",
        "7. Pie de carta: identificación local de BOT-IA.",
        "",
        "✨ UR: marco dorado + realce elemental. El efecto rodea el arte,",
        "sin sustituir ni recortar la pose dinámica del personaje.",
    ]
    return "\n".join(lines)


def build_tutorial_html() -> str:
    """Genera una infografía HTML local, sin recursos externos."""
    rows = []
    for source in ELEMENTS:
        target = ADVANTAGES[source]
        rows.append(
            f"<tr><td><b>{source}</b></td><td>→</td><td><b>{target}</b></td></tr>"
        )
    return (
        "<html><body style='font-family:sans-serif;'>"
        "<h2>📚 TCG / WAIFUMON</h2>"
        "<p><b>Matriz elemental</b>: cada elemento tiene ventaja sobre el siguiente.</p>"
        "<table border='1' cellpadding='8' cellspacing='0'>"
        "<tr><th>Elemento</th><th></th><th>Ventaja</th></tr>"
        + "".join(rows)
        + "</table>"
        "<h3>🃏 Partes de la carta</h3>"
        "<ol>"
        "<li>Marco y rareza (R / SR / UR)</li>"
        "<li>Arte del personaje</li>"
        "<li>Elemento</li>"
        "<li>Nombre / identidad</li>"
        "<li>HP, Ataque y Tipo en Waifumon</li>"
        "<li>Pose, vestimenta o cosplay</li>"
        "<li>Pie de carta BOT-IA</li>"
        "</ol>"
        "<p><b>UR:</b> marco dorado, brillo elemental y efectos de energía "
        "en los bordes para conservar visible el arte dinámico.</p>"
        "</body></html>"
    )
