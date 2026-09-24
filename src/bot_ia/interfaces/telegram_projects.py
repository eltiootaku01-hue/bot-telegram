# -*- coding: utf-8 -*-
from __future__ import annotations

from bot_ia.core.application import BotApplication
from bot_ia.core.project_manager import ProjectError
from bot_ia.interfaces.telegram import TelegramOutbound, parse_callback_update, parse_update
from bot_ia.interfaces.telegram_novel_v2 import TelegramNovelV2Adapter
from bot_ia.runtime import RuntimeComponents


class TelegramProjectsAdapter(TelegramNovelV2Adapter):
    """UI de novela con proyectos persistentes creados por el usuario."""

    MAIN_MENU = (
        (("📖 Novela", "menu:novel"), ("🆕 Nueva novela", "project:new")),
        (("📝 Editar", "menu:edit"), ("📚 Biblioteca", "menu:library")),
        (("🧭 Continuidad", "menu:continuity"), ("💡 Ideas", "menu:ideas")),
        (("🧰 Destrabar escena", "menu:unstick"),),
        (("🔗 Compartir contexto", "menu:share_context"),),
        (("📊 Estado API", "menu:api_status"), ("📈 Progreso", "menu:progress")),
        (("❓ Ayuda", "menu:help"),),
    )

    def __init__(self, application: BotApplication, runtime: RuntimeComponents) -> None:
        super().__init__(application)
        self._runtime = runtime

    def _project_menu(self, chat_id: str) -> TelegramOutbound:
        rows: list[tuple[tuple[str, str], ...]] = []
        for universe_id in self._runtime.configured_universe_ids():
            universe = self._runtime.universe(universe_id)
            prefix = "📖" if universe_id in {"one_neko_punch", "neko_fish_online", "neko_of_the_dead", "my_neko_academia", "attack_on_neko"} else "📝"
            rows.append(((f"{prefix} {universe.definition.display_name}", f"project:select:{universe_id}"),))
        rows.append((("🆕 Nueva novela", "project:new"),))
        rows.append((("⬅️ Menú", "menu:main"),))
        return TelegramOutbound(chat_id, "📚 MIS NOVELAS\n\nElige una novela existente o crea una nueva. Cada proyecto mantiene su biblioteca y memoria aisladas.", "local", tuple(rows))

    def handle_callback(self, update: dict[str, object]) -> TelegramOutbound:
        callback = parse_callback_update(update)
        key = (callback.user_id, callback.conversation_id)
        self._touch_state(key)
        data = callback.data
        if data == "menu:novel":
            return self._project_menu(callback.conversation_id)
        if data == "project:new":
            self._pending[key] = "new_novel"
            return TelegramOutbound(callback.conversation_id, "🆕 NUEVA NOVELA\n\n¿Cómo se llamará la nueva novela?\n\nEscribe el nombre en el próximo mensaje.", "local", (("❌ Cancelar", "menu:main"),))
        if data.startswith("project:select:"):
            universe_id = data.removeprefix("project:select:")
            try:
                universe = self._runtime.universe(universe_id)
                self._application.select_universe(callback.user_id, callback.conversation_id, universe_id)
            except (KeyError, ValueError) as error:
                raise ValueError("project selection is invalid") from error
            reference = None
            try:
                reference = self._runtime.config.universe(universe_id).reference_display_name
            except KeyError:
                pass
            reference_line = f"\nReferencia: {reference}" if reference else ""
            return TelegramOutbound(callback.conversation_id, f"📖 Novela activa: {universe.definition.display_name}\nID: {universe_id}{reference_line}\n\nEsta conversación queda aislada en esta novela.", "local", (("📚 Cambiar novela", "menu:novel"), ("⬅️ Menú", "menu:main")))
        return super().handle_callback(update)

    def handle_update(self, update: dict[str, object]) -> TelegramOutbound:
        if "callback_query" not in update:
            inbound = parse_update(update)
            key = (inbound.user_id, inbound.conversation_id)
            if self._pending.get(key) == "new_novel":
                self._pending.pop(key, None)
                try:
                    record = self._runtime.create_novel(inbound.text, application=self._application)
                    self._application.select_universe(inbound.user_id, inbound.conversation_id, record.project_id)
                except ProjectError as error:
                    return TelegramOutbound(inbound.conversation_id, f"❌ No pude crear la novela.\n\n{error}", "local", (("🆕 Intentar otra vez", "project:new"), ("⬅️ Novelas", "menu:novel")))
                except (OSError, ValueError, RuntimeError) as error:
                    return TelegramOutbound(inbound.conversation_id, f"❌ La novela no pudo quedar registrada de forma segura.\n\n{error}", "local", (("🆕 Intentar otra vez", "project:new"), ("⬅️ Novelas", "menu:novel")))
                return TelegramOutbound(inbound.conversation_id, f"✅ Novela creada: {record.display_name}\n\nID interno: {record.project_id}\nCarpeta: {record.root_path}\n\nYa está seleccionada como novela activa. La biblioteca empieza vacía: BOT-IA sólo aprenderá de lo que agregues.", "local", (("📚 Ver novelas", "menu:novel"), ("⬅️ Menú", "menu:main")))
        return super().handle_update(update)
