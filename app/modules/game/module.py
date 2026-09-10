from aiogram import F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.core.module import BotModule
from app.game.catalog import get_character
from app.game.engine import GameEngine
from app.ui.game_keyboards import combat_keyboard, gacha_keyboard


class GameModule(BotModule):
    name = "game"

    def __init__(self) -> None:
        super().__init__()
        self.engine = GameEngine()

    def setup(self) -> None:
        self.router.message.register(self.gacha, Command("gacha"))
        self.router.message.register(self.combat, Command("combate"))
        self.router.callback_query.register(self.gacha_roll, F.data == "game:gacha:roll")
        self.router.callback_query.register(self.combat_action, F.data.startswith("game:combat:"))

    async def gacha(self, message: Message) -> None:
        await message.answer(
            "🎰 <b>Gacha de personajes</b>\n\n"
            "Las rarezas y las ilustraciones subirán de nivel con el sistema de gacha.",
            reply_markup=gacha_keyboard(),
        )

    async def gacha_roll(self, callback: CallbackQuery) -> None:
        rarity = self.engine.roll_gacha(seed=str(callback.id))
        await callback.answer(f"¡Salió {rarity.value.upper()}!", show_alert=True)

    async def combat(self, message: Message) -> None:
        taiga = get_character("taiga")
        await message.answer(
            f"⚔️ <b>{taiga.name}</b> — {taiga.anime}\n\n"
            f"Ataque: {taiga.attack_name}\n"
            f"Defensa: {taiga.defense_name}\n"
            f"Especial: {taiga.special_name}\n\n"
            "Elegí una acción para probar el sistema de combate.",
            reply_markup=combat_keyboard(),
        )

    async def combat_action(self, callback: CallbackQuery) -> None:
        action_key = callback.data.rsplit(":", 1)[-1]
        taiga = get_character("taiga")
        result = self.engine.combat(taiga, taiga, action_key, callback.id)
        critical = " 💥 CRÍTICO" if result.critical else ""
        await callback.answer(
            f"{result.action.label}: {result.damage} daño{critical}",
            show_alert=True,
        )
