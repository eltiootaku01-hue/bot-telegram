from __future__ import annotations

from bot_ia.core.application import ApplicationRequest, BotApplication
from bot_ia.interfaces.telegram import TelegramOutbound, parse_callback_update, parse_update
from bot_ia.interfaces.telegram_ui import TelegramNovelAdapter


EDITOR_MENU = (
    (("✏️ Corregir redacción", "edit:wording"), ("🎭 Mejorar emociones", "edit:emotion")),
    (("💬 Revisar diálogos", "edit:dialogue"), ("👁️ Revisar focalización", "edit:pov")),
    (("📖 Revisar continuidad", "edit:continuity"), ("🔍 Buscar contradicciones", "edit:contradictions")),
    (("✨ Pulir capítulo completo", "edit:chapter"),),
    (("⬅️ Menú", "menu:main"),),
)

EDITOR_REQUESTS = {
    "edit:wording": "Corrige la redacción del texto que te voy a proporcionar, sin cambiar hechos, canon, personalidad ni continuidad.",
    "edit:emotion": "Revisa y mejora las emociones del texto que te voy a proporcionar, sin inventar hechos ni cambiar la intención de la escena.",
    "edit:dialogue": "Revisa los diálogos del texto que te voy a proporcionar: naturalidad, voces, ritmo y coherencia, sin alterar hechos establecidos.",
    "edit:pov": "Revisa la focalización del texto que te voy a proporcionar usando tercera persona con focalización cercana y cámara narrativa móvil, sin cambiar el contenido establecido.",
    "edit:continuity": "Revisa la continuidad del texto que te voy a proporcionar contra la biblioteca local del proyecto y señala cualquier contradicción con evidencia.",
    "edit:contradictions": "Busca contradicciones entre el texto que te voy a proporcionar y la biblioteca local. Separa contradicciones confirmadas de posibles dudas.",
    "edit:chapter": "Haz una revisión editorial completa del capítulo que te voy a proporcionar: redacción, emociones, diálogos, focalización, ritmo y continuidad. No conviertas propuestas en canon.",
}


class TelegramNovelV2Adapter(TelegramNovelAdapter):
    """UI de novela ampliada, con selección segura de archivos."""

    MAIN_MENU = (
        (("📖 Novela", "menu:novel"), ("📝 Editar", "menu:edit")),
        (("📚 Biblioteca", "menu:library"), ("🧭 Continuidad", "menu:continuity")),
        (("💡 Ideas", "menu:ideas"), ("🔎 Investigar", "menu:research")),
        (("🧰 Destrabar escena", "menu:unstick"),),
        (("📊 Estado API", "menu:api_status"), ("📈 Progreso", "menu:progress")),
        (("❓ Ayuda", "menu:help"),),
    )

    def __init__(self, application: BotApplication) -> None:
        super().__init__(application)
        self._selected_main: dict[tuple[str, str], str] = {}
        self._selected_secondary: dict[tuple[str, str], str] = {}

    def handle_callback(self, update: dict[str, object]) -> TelegramOutbound:
        callback = parse_callback_update(update)
        key = (callback.user_id, callback.conversation_id)
        data = callback.data
        if data == "menu:edit":
            return TelegramOutbound(callback.conversation_id, "📝 EDITOR\n\nElige qué quieres revisar.", "local", EDITOR_MENU)
        if data in EDITOR_REQUESTS:
            self._pending[key] = data
            return TelegramOutbound(
                callback.conversation_id,
                "📂 ¿Cómo quieres proporcionar el texto? Puedes pegarlo directamente o elegir un archivo de la biblioteca.",
                "local",
                (("📂 Elegir archivo principal", "edit:file:main"),),
                )
        if data == "edit:file:main":
            return self._file_menu(callback.user_id, callback.conversation_id, secondary=False)
        if data == "edit:file:secondary":
            return self._file_menu(callback.user_id, callback.conversation_id, secondary=True)
        if data.startswith("edit:select:"):
            source_id = data.removeprefix("edit:select:")
            return self._select_file(callback.user_id, callback.conversation_id, source_id, secondary=False)
        if data.startswith("edit:select2:"):
            source_id = data.removeprefix("edit:select2:")
            return self._select_file(callback.user_id, callback.conversation_id, source_id, secondary=True)
        if data == "edit:run":
            return self._run_selected(callback.user_id, callback.conversation_id)
        if data == "menu:research":
            self._pending[key] = "research"
            return TelegramOutbound(
                callback.conversation_id,
                "🔎 INVESTIGAR\n\nEscribe la pregunta. BOT-IA buscará primero en la biblioteca y no usará una API sin autorización explícita.",
                "local",
                (("⬅️ Menú", "menu:main"),),
            )
        if data == "menu:library":
            return self._library_menu(callback.user_id, callback.conversation_id)
        if data == "menu:main":
            self._pending.pop(key, None)
            self._selected_main.pop(key, None)
            self._selected_secondary.pop(key, None)
        return super().handle_callback(update)

    def handle_update(self, update: dict[str, object]) -> TelegramOutbound:
        if "callback_query" not in update:
            inbound = parse_update(update)
            key = (inbound.user_id, inbound.conversation_id)
            pending = self._pending.get(key)
            if pending == "research":
                self._pending.pop(key, None)
                response = self._application.handle(ApplicationRequest(inbound.user_id, inbound.conversation_id, inbound.text))
                return self.from_response(inbound.conversation_id, response)
            if pending in EDITOR_REQUESTS:
                self._pending.pop(key, None)
                request = EDITOR_REQUESTS[pending] + "\n\nTEXTO DEL USUARIO:\n" + inbound.text
                response = self._application.handle(ApplicationRequest(inbound.user_id, inbound.conversation_id, request))
                return self.from_response(inbound.conversation_id, response)
        return super().handle_update(update)

    def _entries_for(self, user_id: str, chat_id: str):
        executor = getattr(self._application, "_executor", None)
        entries = getattr(executor, "_entries", {}) if executor is not None else {}
        universe_id = "one_neko_punch"
        try:
            state = self._application._sessions.get(user_id, chat_id)
            if state is not None:
                universe_id = state.universe_id
        except Exception:
            pass
        return universe_id, entries.get(universe_id, ())

    def _file_menu(self, user_id: str, chat_id: str, *, secondary: bool) -> TelegramOutbound:
        universe_id, entries = self._entries_for(user_id, chat_id)
        if not entries:
            return TelegramOutbound(chat_id, "📂 No hay archivos indexados para la novela activa.", "local", (("⬅️ Editor", "menu:edit"),))
        rows = []
        prefix = "edit:select2:" if secondary else "edit:select:"
        for entry in entries[:12]:
            record = getattr(entry, "record", None)
            source_id = str(getattr(record, "source_id", ""))
            path = str(getattr(record, "path", source_id))
            if source_id:
                rows.append(((path[-48:], prefix + source_id),))
        rows.append((("⬅️ Editor", "menu:edit"),))
        title = "📎 ARCHIVO SECUNDARIO" if secondary else "📂 ARCHIVO PRINCIPAL"
        return TelegramOutbound(chat_id, f"{title}\n\nNovela: {universe_id}\nSelecciona una fuente indexada:", "local", tuple(rows))

    def _select_file(self, user_id: str, chat_id: str, source_id: str, *, secondary: bool) -> TelegramOutbound:
        key = (user_id, chat_id)
        _, entries = self._entries_for(user_id, chat_id)
        entry = next((item for item in entries if getattr(getattr(item, "record", None), "source_id", "") == source_id), None)
        if entry is None:
            return TelegramOutbound(chat_id, "No encontré ese archivo en la biblioteca activa. No ejecutaré una selección ambigua.", "local", (("⬅️ Editor", "menu:edit"),))
        if secondary:
            self._selected_secondary[key] = source_id
        else:
            self._selected_main[key] = source_id
        path = getattr(getattr(entry, "record", None), "path", source_id)
        keyboard = (("▶️ Ejecutar revisión", "edit:run"), ("📎 Añadir secundario", "edit:file:secondary"), ("⬅️ Editor", "menu:edit"))
        return TelegramOutbound(chat_id, f"Seleccionado: {path}\n\nAhora puedes ejecutar la revisión o añadir un segundo archivo como contexto.", "local", keyboard)

    def _run_selected(self, user_id: str, chat_id: str) -> TelegramOutbound:
        key = (user_id, chat_id)
        action = self._pending.get(key)
        main_id = self._selected_main.get(key)
        if action not in EDITOR_REQUESTS or not main_id:
            return TelegramOutbound(chat_id, "Primero elige una revisión y un archivo principal.", "local", EDITOR_MENU)
        _, entries = self._entries_for(user_id, chat_id)
        main = next((item for item in entries if getattr(getattr(item, "record", None), "source_id", "") == main_id), None)
        if main is None:
            return TelegramOutbound(chat_id, "El archivo principal ya no está disponible en la biblioteca activa.", "local", (("⬅️ Editor", "menu:edit"),))
        request = EDITOR_REQUESTS[action] + "\n\nARCHIVO PRINCIPAL:\n" + str(getattr(main, "content", ""))
        secondary_id = self._selected_secondary.get(key)
        if secondary_id:
            secondary = next((item for item in entries if getattr(getattr(item, "record", None), "source_id", "") == secondary_id), None)
            if secondary is not None:
                request += "\n\nARCHIVO SECUNDARIO / CONTEXTO:\n" + str(getattr(secondary, "content", ""))
        self._pending.pop(key, None)
        self._selected_main.pop(key, None)
        self._selected_secondary.pop(key, None)
        response = self._application.handle(ApplicationRequest(user_id, chat_id, request))
        return self.from_response(chat_id, response)

    def _library_menu(self, user_id: str, chat_id: str) -> TelegramOutbound:
        universe_id, current = self._entries_for(user_id, chat_id)
        if not current:
            text = "📚 BIBLIOTECA\n\nNo hay fuentes indexadas para la novela activa. BOT-IA no inventará contenido."
        else:
            lines = [f"📚 BIBLIOTECA — {universe_id}", "", f"Fuentes indexadas: {len(current)}", ""]
            for entry in current[:12]:
                record = getattr(entry, "record", None)
                lines.append(f"• {getattr(record, 'path', '')} [{getattr(record, 'source_type', '')}]")
            if len(current) > 12:
                lines.append(f"… y {len(current) - 12} fuente(s) más.")
            text = "\n".join(lines)
        return TelegramOutbound(chat_id, text, "local", (("📝 Editor", "menu:edit"), ("⬅️ Menú", "menu:main")))
