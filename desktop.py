# -*- coding: utf-8 -*-
"""Compatibilidad de lanzamiento para la nueva UI Qt de Café Otaku.

El backend y la UI real viven en src/gui. Este módulo conserva el nombre
histórico desktop para scripts y tests antiguos sin mantener una segunda
implementación de interfaz.
"""

from __future__ import annotations

from gui.app import CafeOtakuWindow, main as qt_main


MENU_ACTIONS = {
    "📖 Novela": "Quiero trabajar en la novela activa.",
    "📚 Biblioteca": "¿Qué información y documentos tengo disponibles en la biblioteca local?",
    "🧭 Continuidad": "Quiero revisar la continuidad de lo que estamos escribiendo y saber dónde quedamos.",
    "💡 Ideas": "Quiero ideas para continuar la novela usando la continuidad y personajes establecidos.",
    "🔎 Investigar": "Quiero investigar una duda usando primero la biblioteca local.",
    "🧰 Destrabar escena": None,
    "🔗 Compartir contexto": None,
    "📊 Estado API": None,
    "📈 Progreso": None,
    "❓ Ayuda": "¿Cómo funciona BOT-IA y qué puede hacer?",
}


class BotIADesktop(CafeOtakuWindow):
    """Alias histórico de la ventana principal."""

    def start_telegram(self, button=None):
        return super().start_telegram(button)


def main() -> int:
    return qt_main()


if __name__ == "__main__":
    raise SystemExit(main())
