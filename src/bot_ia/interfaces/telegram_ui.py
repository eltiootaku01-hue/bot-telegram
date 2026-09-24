# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import re
from collections import OrderedDict

from bot_ia.core.application import ApplicationRequest, BotApplication
from bot_ia.core.context_selection import available_context_sources, select_context_sources
from bot_ia.core.context_sharing import build_shared_context
from bot_ia.core.creative_assist import build_stuck_menu, expand_scene_sketch
from bot_ia.librarian.models import CoverageStatus
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
        (("🔗 Compartir contexto", "menu:share_context"),),
        (("📊 Estado API", "menu:api_status"), ("📈 Progreso", "menu:progress")),
        (("❓ Ayuda", "menu:help"),),
    )

    MAX_UI_SESSION_STATES = 512

    def __init__(self, application: BotApplication) -> None:
        super().__init__(application)
        self._pending: dict[tuple[str, str], str] = {}
        self._last_message: dict[tuple[str, str], str] = {}
        self._last_execution: dict[tuple[str, str], object] = {}
        self._context_selection: dict[tuple[str, str], set[int]] = {}
        self._fallback_query: dict[tuple[str, str], str] = {}
        self._state_activity: OrderedDict[tuple[str, str], None] = OrderedDict()

    def _touch_state(self, key: tuple[str, str]) -> None:
        self._state_activity.pop(key, None)
        self._state_activity[key] = None
        while len(self._state_activity) > self.MAX_UI_SESSION_STATES:
            oldest, _ = self._state_activity.popitem(last=False)
            self._pending.pop(oldest, None)
            self._last_message.pop(oldest, None)
            self._last_execution.pop(oldest, None)
            self._context_selection.pop(oldest, None)
            self._fallback_query.pop(oldest, None)

    def handle_update(self, update: dict[str, object]) -> TelegramOutbound:
        if "callback_query" in update:
            return self.handle_callback(update)
        inbound = parse_update(update)
        key = (inbound.user_id, inbound.conversation_id)
        self._touch_state(key)
        self._last_message[key] = inbound.text
        self._fallback_query.pop(key, None)
        pending = self._pending.pop(key, None)
        if pending == "local":
            return TelegramOutbound(inbound.conversation_id, expand_scene_sketch(inbound.text), "local", (("🧰 Otra ronda", "menu:unstick"), ("⬅️ Menú", "menu:main")))
        if pending == "api":
            response = self._application.handle(ApplicationRequest(inbound.user_id, inbound.conversation_id, inbound.text, allow_external_api=True))
            self._remember_execution(
                key,
                response,
                fallback_query=inbound.text,
            )
            return self.from_response(inbound.conversation_id, response)
        if pending == "prompt":
            return TelegramOutbound(inbound.conversation_id, self._build_prompt(inbound.text), "local", (("⬅️ Menú", "menu:main"),))
        command = inbound.text.casefold().split()[0]
        if command in {"/start", "/menu"}:
            return TelegramOutbound(inbound.conversation_id, "¿Qué quieres hacer?", "local", self.MAIN_MENU)
        if command == "/help":
            return TelegramOutbound(inbound.conversation_id, "Usa los botones para elegir novela, editar, consultar la biblioteca, revisar continuidad, compartir contexto, ver el estado de APIs, ver el progreso o destrabar una escena.", "local", self.MAIN_MENU)
        response = self._application.handle(ApplicationRequest(inbound.user_id, inbound.conversation_id, inbound.text))
        self._remember_execution(
            key,
            response,
            fallback_query=inbound.text,
        )
        return self.from_response(inbound.conversation_id, response)

    def _remember_execution(
        self,
        key: tuple[str, str],
        response: object,
        *,
        fallback_query: str | None = None,
    ) -> None:
        execution = getattr(response, "execution", None)
        if execution is not None:
            self._last_execution[key] = execution
            self._context_selection.pop(key, None)
            evidence = getattr(execution, "evidence", None)
            coverage = getattr(evidence, "coverage", None)
            status = getattr(coverage, "status", None)
            if (
                fallback_query and
                status in {CoverageStatus.NO_ENCONTRADO, CoverageStatus.NO_ESTABLECIDO}
            ):
                self._fallback_query[key] = fallback_query
            else:
                self._fallback_query.pop(key, None)

    def handle_callback(self, update: dict[str, object]) -> TelegramOutbound:
        callback = parse_callback_update(update)
        key = (callback.user_id, callback.conversation_id)
        self._touch_state(key)
        data = callback.data
        if data == "menu:novel":
            return TelegramOutbound(callback.conversation_id, "📖 ¿Qué novela quieres trabajar?\n\nEl canon será el de la novela elegida. La obra original queda como referencia, no como canon.", "local", NOVEL_MENU)
        if data in NOVEL_PROFILES:
            name, universe_id, reference = NOVEL_PROFILES[data]
            if universe_id == "one_neko_punch":
                response = self._application.handle(ApplicationRequest(callback.user_id, callback.conversation_id, "Quiero trabajar en One Neko Punch."))
                self._remember_execution(key, response)
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
        if data == "menu:share_context":
            return self._context_menu(key, callback.conversation_id)
        if data.startswith("context:toggle:"):
            return self._context_toggle(key, callback.conversation_id, data.removeprefix("context:toggle:"))
        if data == "context:send":
            return self._context_send(key, callback.conversation_id)
        if data == "context:all":
            execution = self._last_execution.get(key)
            if execution is None:
                return TelegramOutbound(callback.conversation_id, "🔗 No hay una consulta con evidencia para compartir.", "local", self.MAIN_MENU)
            self._context_selection[key] = set(range(len(available_context_sources(execution))))
            return self._context_menu(key, callback.conversation_id)
        if data == "context:none":
            self._context_selection[key] = set()
            return self._context_menu(key, callback.conversation_id)
        if data == "menu:api_status":
            return self._api_status(callback.conversation_id)
        if data == "menu:progress":
            return self._chapter_progress(callback.conversation_id)
        if data == "fallback:api":
            original = self._fallback_query.get(key)
            if not original:
                return TelegramOutbound(callback.conversation_id, "La autorización de esta consulta ya no está disponible. Envía la pregunta nuevamente.", "local", self.MAIN_MENU)
            response = self._application.handle(ApplicationRequest(callback.user_id, callback.conversation_id, original, allow_external_api=True))
            self._remember_execution(key, response)
            return self.from_response(callback.conversation_id, response)
        if data == "fallback:prompt":
            original = self._fallback_query.get(key)
            if not original:
                return TelegramOutbound(callback.conversation_id, "La consulta asociada a este botón ya no está disponible. Envía la pregunta nuevamente.", "local", (("⬅️ Menú", "menu:main"),))
            return TelegramOutbound(callback.conversation_id, self._build_prompt(original), "local", (("⬅️ Menú", "menu:main"),))
        if data == "menu:main":
            self._pending.pop(key, None)
            self._context_selection.pop(key, None)
            self._fallback_query.pop(key, None)
            return TelegramOutbound(callback.conversation_id, "Menú principal:", "local", self.MAIN_MENU)
        return super().handle_callback(update)

    def _context_menu(self, key: tuple[str, str], chat_id: str) -> TelegramOutbound:
        execution = self._last_execution.get(key)
        if execution is None:
            return TelegramOutbound(chat_id, "🔗 No hay una consulta procesada con evidencia para compartir. Primero realiza una consulta a BOT-IA.", "local", self.MAIN_MENU)
        source_ids = available_context_sources(execution)
        if not source_ids:
            return TelegramOutbound(chat_id, "🔗 La última consulta no recuperó fuentes compartibles. BOT-IA no buscará archivos adicionales desde este menú.", "local", (("⬅️ Menú", "menu:main"),))
        selected = self._context_selection.setdefault(key, set(range(len(source_ids))))
        buttons: list[tuple[tuple[str, str], ...]] = []
        for index, source_id in enumerate(source_ids):
            marker = "☑️" if index in selected else "⬜"
            buttons.append(((f"{marker} {index + 1}. {source_id[:42]}", f"context:toggle:{index}"),))
        buttons.append((("☑️ Todas", "context:all"), ("⬜ Ninguna", "context:none")))
        buttons.append(((f"📋 Generar paquete ({len(selected)}/{len(source_ids)})", "context:send"),))
        buttons.append((("⬅️ Menú", "menu:main"),))
        text = (
            "🔗 COMPARTIR CONTEXTO\n\n"
            f"Universo: {execution.evidence.query.universe_id}\n"
            "Sólo puedes seleccionar evidencia ya recuperada por esta consulta.\n"
            "BOT-IA no descubre archivos nuevos ni envía el paquete automáticamente.\n\n"
            "Selecciona las fuentes que quieras incluir:"
        )
        return TelegramOutbound(chat_id, text, "local", tuple(buttons))

    def _context_toggle(self, key: tuple[str, str], chat_id: str, raw_index: str) -> TelegramOutbound:
        execution = self._last_execution.get(key)
        if execution is None:
            return TelegramOutbound(chat_id, "🔗 La consulta de contexto ya no está disponible. Ejecuta otra consulta.", "local", self.MAIN_MENU)
        try:
            index = int(raw_index)
        except ValueError:
            raise ValueError("context source index is invalid")
        source_ids = available_context_sources(execution)
        if index < 0 or index >= len(source_ids):
            raise ValueError("context source index is outside the retrieved evidence")
        selected = self._context_selection.setdefault(key, set(range(len(source_ids))))
        if index in selected:
            selected.remove(index)
        else:
            selected.add(index)
        return self._context_menu(key, chat_id)

    def _context_send(self, key: tuple[str, str], chat_id: str) -> TelegramOutbound:
        execution = self._last_execution.get(key)
        if execution is None:
            return TelegramOutbound(chat_id, "🔗 No hay evidencia disponible para compartir.", "local", self.MAIN_MENU)
        source_ids = available_context_sources(execution)
        selected_indices = self._context_selection.get(key, set())
        if not selected_indices:
            return TelegramOutbound(chat_id, "🔗 No seleccionaste ninguna fuente. Elige al menos una antes de generar el paquete.", "local", self._context_menu(key, chat_id).keyboard)
        selected_ids = tuple(source_ids[index] for index in sorted(selected_indices))
        selected_execution = select_context_sources(execution, selected_ids)
        shared = build_shared_context(selected_execution)
        self._context_selection.pop(key, None)
        text = (
            "📦 PAQUETE DE CONTEXTO GENERADO\n\n"
            "BOT-IA no lo envió a ninguna IA externa. Copia este contenido y pégalo donde quieras.\n\n"
            + shared.as_external_prompt()
        )
        return TelegramOutbound(chat_id, text, "local", (("🔗 Compartir otro contexto", "menu:share_context"), ("⬅️ Menú", "menu:main")))

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
                consumed = max(0.0, min(100.0, 100.0 * used / budget))
                remaining = 100.0 - consumed
                lines.append(f"• {provider}/{account}: 🔋 {remaining:.1f}% restante ({consumed:.1f}% consumido), estado={state}")
            else:
                lines.append(f"• {provider}/{account}: {used:,} tokens conocidos, estado={state}; batería porcentual no calculable")
        lines.append("La batería porcentual usa un presupuesto local configurado; no representa el saldo real del proveedor.")
        return TelegramOutbound(chat_id, "\n".join(lines), "local", (("⬅️ Menú", "menu:main"),))

    def _chapter_progress(self, chat_id: str) -> TelegramOutbound:
        executor = getattr(self._application, "_executor", None)
        entries = getattr(executor, "_entries", {}) if executor is not None else {}
        universe_id = os.getenv("BOT_IA_UNIVERSE", "one_neko_punch")
        paths = [getattr(getattr(entry, "record", None), "path", "") for entry in entries.get(universe_id, ())]
        chapters = sorted({int(n) for path in paths for n in re.findall(r"(?:cap(?:ítulo)?|cap)[ _-]?(\d+)", path.casefold())})
        target = int(os.getenv("BOT_IA_TARGET_CHAPTERS", "0") or "0")
        if target > 0:
            pct = min(100.0, 100.0 * len(chapters) / target)
            text = f"📈 PROGRESO DE CAPÍTULOS\n\nCapítulos detectados: {len(chapters)}\nObjetivo configurado: {target}\nCobertura documental: {pct:.1f}%\n\nNo es porcentaje de calidad ni de historia terminada; sólo mide capítulos documentados frente al objetivo configurado."
        else:
            text = f"📈 PROGRESO DE CAPÍTULOS\n\nCapítulos detectados en la biblioteca: {len(chapters)}\n\nEl porcentaje todavía no es calculable porque no hay un objetivo total configurado. Usa BOT_IA_TARGET_CHAPTERS para definirlo; BOT-IA no inventará un total."
        return TelegramOutbound(chat_id, text, "local", (("⬅️ Menú", "menu:main"),))

    @staticmethod
    def _build_prompt(question: str) -> str:
        question = question.strip() or "la consulta del usuario"
        return f"PROMPT PARA OTRA IA\n\nAyúdame a desarrollar esta consulta de una novela. Separa hechos establecidos, inferencias y propuestas nuevas. No conviertas propuestas en canon sin indicarlo.\n\nCONSULTA:\n{question}\n\nCONTEXTO QUE PROPORCIONARÉ:\nUsa únicamente el material que te entregue."
