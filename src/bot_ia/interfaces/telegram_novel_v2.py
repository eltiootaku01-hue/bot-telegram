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
    """UI de novela ampliada sin reemplazar el núcleo de BOT-IA."""

    def handle_callback(self, update: dict[str, object]) -> TelegramOutbound:
        callback = parse_callback_update(update)
        if callback.data == "menu:edit":
            return TelegramOutbound(
                callback.conversation_id,
                "📝 EDITOR\n\nElige qué quieres revisar. Luego envía el texto que quieres analizar.",
                "local",
                EDITOR_MENU,
            )
        if callback.data in EDITOR_REQUESTS:
            self._pending[(callback.user_id, callback.conversation_id)] = callback.data
            return TelegramOutbound(
                callback.conversation_id,
                "📂 Envía ahora el texto que quieres revisar.\n\nLa biblioteca se usará como evidencia de continuidad; la API no se usará silenciosamente.",
                "local",
                (("❌ Cancelar", "menu:main"),),
            )
        if callback.data == "menu:library":
            return self._library_menu(callback.user_id, callback.conversation_id)
        return super().handle_callback(update)

    def handle_update(self, update: dict[str, object]) -> TelegramOutbound:
        if "callback_query" not in update:
            inbound = parse_update(update)
            key = (inbound.user_id, inbound.conversation_id)
            pending = self._pending.get(key)
            if pending in EDITOR_REQUESTS:
                self._pending.pop(key, None)
                request = EDITOR_REQUESTS[pending] + "\n\nTEXTO DEL USUARIO:\n" + inbound.text
                response = self._application.handle(ApplicationRequest(inbound.user_id, inbound.conversation_id, request))
                return self.from_response(inbound.conversation_id, response)
        return super().handle_update(update)

    def _library_menu(self, user_id: str, chat_id: str) -> TelegramOutbound:
        executor = getattr(self._application, "_executor", None)
        entries = getattr(executor, "_entries", {}) if executor is not None else {}
        universe_id = "one_neko_punch"
        try:
            state = self._application._sessions.get(user_id, chat_id)
            if state is not None:
                universe_id = state.universe_id
        except Exception:
            pass
        current = entries.get(universe_id, ())
        if not current:
            text = "📚 BIBLIOTECA\n\nNo hay fuentes indexadas para la novela activa. BOT-IA no inventará contenido."
        else:
            lines = [f"📚 BIBLIOTECA — {universe_id}", "", f"Fuentes indexadas: {len(current)}", ""]
            for entry in current[:12]:
                record = getattr(entry, "record", None)
                path = getattr(record, "path", "")
                source_type = getattr(record, "source_type", "")
                lines.append(f"• {path} [{source_type}]")
            if len(current) > 12:
                lines.append(f"… y {len(current) - 12} fuente(s) más.")
            text = "\n".join(lines)
        return TelegramOutbound(chat_id, text, "local", (("📝 Editor", "menu:edit"), ("⬅️ Menú", "menu:main")))
