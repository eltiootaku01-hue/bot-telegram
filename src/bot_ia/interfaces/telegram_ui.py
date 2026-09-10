from __future__ import annotations

import os

from bot_ia.core.application import ApplicationRequest, BotApplication
from bot_ia.core.creative_assist import build_stuck_menu, expand_scene_sketch
from bot_ia.interfaces.telegram import TelegramAdapter, TelegramOutbound, parse_callback_update, parse_update

NOVEL_MENU = ((("🐱 One Neko Punch", "novel:one_neko_punch"),), (("⚔️ Neko Fish Online", "novel:neko_fish_online"),), (("🧟 Neko of the Dead", "novel:neko_of_the_dead"),), (("🦸 My Neko Academia", "novel:my_neko_academia"),), (("🧱 Attack on Neko", "novel:attack_on_neko"),), (("⬅️ Menú", "menu:main"),))
NOVEL_PROFILES = {
    "novel:one_neko_punch": ("One Neko Punch", "one_neko_punch", "One-Punch Man"),
    "novel:neko_fish_online": ("Neko Fish Online", "neko_fish_online", "Sword Art Online"),
    "novel:neko_of_the_dead": ("Neko of the Dead", "neko_of_the_dead", "Highschool of the Dead"),
    "novel:my_neko_academia": ("My Neko Academia", "my_neko_academia", "My Hero Academia"),
    "novel:attack_on_neko": ("Attack on Neko", "attack_on_neko", "Attack on Titan"),
}


class TelegramNovelAdapter(TelegramAdapter):
    MAIN_MENU = (
        (("📖 Novela", "menu:novel"), ("📝 Editar", "menu:edit")),
        (("📚 Biblioteca", "menu:library"), ("🧭 Continuidad", "menu:continuity")),
        (("💡 Ideas", "menu:ideas"), ("🧰 Destrabar escena", "menu:unstick")),
        (("📊 Estado API", "menu:api_status"), ("❓ Ayuda", "menu:help")),
    )

    def __init__(self, application: BotApplication) -> None:
        super().__init__(application)
        self._pending: dict[tuple[str, str], str] = {}
        self._last_message: dict[tuple[str, str], str] = {}

    def handle_update(self, update: dict[str, object]) -> TelegramOutbound:
        if "callback_query" in update:
            return self.handle_callback(update)
        inbound = parse_update(update)
        key = (inbound.user_id, inbound.conversation_id)
        self._last_message[key] = inbound.text
        pending = self._pending.pop(key, None)
        if pending == "local":
            return TelegramOutbound(inbound.conversation_id, expand_scene_sketch(inbound.text), "local", (("🧰 Otra ronda", "menu:unstick"), ("⬅️ Menú", "menu:main")))
        if pending == "api":
            response = self._application.handle(ApplicationRequest(inbound.user_id, inbound.conversation_id, inbound.text, allow_external_api=True))
            return self.from_response(inbound.conversation_id, response)
        if pending == "prompt":
            return TelegramOutbound(inbound.conversation_id, self._build_prompt(inbound.text), "local", (("⬅️ Menú", "menu:main"),))
        command = inbound.text.casefold().split()[0]
        if command in {"/start", "/menu"}:
            return TelegramOutbound(inbound.conversation_id, "¿Qué quieres hacer?", "local", self.MAIN_MENU)
        if command == "/help":
            return TelegramOutbound(inbound.conversation_id, "Usa los botones para elegir novela, editar, consultar la biblioteca, revisar continuidad, ver el estado de APIs o destrabar una escena.", "local", self.MAIN_MENU)
        response = self._application.handle(ApplicationRequest(inbound.user_id, inbound.conversation_id, inbound.text))
        return self.from_response(inbound.conversation_id, response)

    def handle_callback(self, update: dict[str, object]) -> TelegramOutbound:
        callback = parse_callback_update(update)
        key = (callback.user_id, callback.conversation_id)
        data = callback.data
        if data == "menu:novel":
            return TelegramOutbound(callback.conversation_id, "📖 ¿Qué novela quieres trabajar?\n\nEl canon será el de la novela elegida. La obra original queda como referencia, no como canon.", "local", NOVEL_MENU)
        if data in NOVEL_PROFILES:
            name, universe_id, reference = NOVEL_PROFILES[data]
            if universe_id == "one_neko_punch":
                response = self._application.handle(ApplicationRequest(callback.user_id, callback.conversation_id, "Quiero trabajar en One Neko Punch."))
                text = f"📖 Novela activa: {name}\nCanon: {name}\nReferencia: {reference}\n\n{response.text}"
                return TelegramOutbound(callback.conversation_id, text, response.decision.route.value, (("📖 Cambiar novela", "menu:novel"), ("⬅️ Menú", "menu:main")))
            text = f"📖 {name}\nCanon: {name}\nReferencia: {reference}\n\nLa ficha está definida, pero su carpeta de canon todavía no está conectada al runtime. No la mezclaré con otra novela."
            return TelegramOutbound(callback.conversation_id, text, "local", (("📖 Cambiar novela", "menu:novel"), ("⬅️ Menú", "menu:main")))
        if data == "menu:unstick":
            return TelegramOutbound(callback.conversation_id, "🧰 Destrabar escena\n\nPuedes escribir el hueco aunque sean 3–10 palabras. BOT-IA puede convertirlo en preguntas de desarrollo sin consumir API.", "local", build_stuck_menu())
        if data == "stuck:local":
            self._pending[key] = "local"
            return TelegramOutbound(callback.conversation_id, "Escribe ahora tu boceto corto. Ejemplo: «Kuro salva a alguien, camina y se va».", "local", (("⬅️ Menú", "menu:main"),))
        if data == "stuck:api":
            self._pending[key] = "api"
            return TelegramOutbound(callback.conversation_id, "🔐 API autorizada para la próxima consulta. Escribe el boceto o pregunta. Esta autorización sólo afecta a esa petición.", "local", (("❌ Cancelar", "menu:main"),))
        if data == "stuck:prompt":
            self._pending[key] = "prompt"
            return TelegramOutbound(callback.conversation_id, "📋 Escribe el boceto y prepararé un prompt para otra IA sin llamar a ninguna API.", "local", (("⬅️ Menú", "menu:main"),))
        if data == "menu:api_status":
            return self._api_status(callback.conversation_id)
        if data == "fallback:api":
            original = self._last_message.get(key)
            if not original:
                return TelegramOutbound(callback.conversation_id, "No tengo una consulta pendiente para autorizar.", "local", self.MAIN_MENU)
            response = self._application.handle(ApplicationRequest(callback.user_id, callback.conversation_id, original, allow_external_api=True))
            return self.from_response(callback.conversation_id, response)
        if data == "fallback:prompt":
            original = self._last_message.get(key, "")
            return TelegramOutbound(callback.conversation_id, self._build_prompt(original), "local", (("⬅️ Menú", "menu:main"),))
        if data == "menu:main":
            self._pending.pop(key, None)
            return TelegramOutbound(callback.conversation_id, "Menú principal:", "local", self.MAIN_MENU)
        return super().handle_callback(update)

    def _api_status(self, chat_id: str) -> TelegramOutbound:
        lines = ["📊 ESTADO DE APIs"]
        manager = getattr(getattr(self._application, "_executor", None), "_provider_manager", None)
        health = getattr(manager, "_health", {}) if manager is not None else {}
        budget = int(os.getenv("BOT_IA_API_BUDGET_TOKENS", "0") or "0")
        if not health:
            lines.append("Todavía no hay datos de uso conocidos.")
        for (provider, account), record in sorted(health.items()):
            used = int(getattr(record, "total_tokens", 0))
            state = getattr(getattr(record, "state", None), "value", "unknown")
            if budget > 0:
                pct = max(0.0, min(100.0, 100.0 * used / budget))
                lines.append(f"• {provider}/{account}: {pct:.1f}% del presupuesto configurado ({used:,}/{budget:,} tokens), estado={state}")
            else:
                lines.append(f"• {provider}/{account}: {used:,} tokens conocidos, estado={state}; porcentaje no calculable")
        lines.append("El porcentaje sólo representa el presupuesto local configurado; no es el saldo real del proveedor.")
        return TelegramOutbound(chat_id, "\n".join(lines), "local", (("⬅️ Menú", "menu:main"),))

    @staticmethod
    def _build_prompt(question: str) -> str:
        question = question.strip() or "la consulta del usuario"
        return f"PROMPT PARA OTRA IA\n\nAyúdame a desarrollar esta consulta de una novela. Separa hechos establecidos, inferencias y propuestas nuevas. No conviertas propuestas en canon sin indicarlo.\n\nCONSULTA:\n{question}\n\nCONTEXTO QUE PROPORCIONARÉ:\nUsa únicamente el material que te entregue."
