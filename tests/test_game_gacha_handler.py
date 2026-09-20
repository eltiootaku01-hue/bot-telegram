from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.db.database import Database
from app.db.models import Chat, GameGachaRoll, GameProfile, PointTransaction, RareDropApproval, User
from app.game.engine import GameEngine
from app.game.gacha import GACHA_COST_POINTS, GachaService
from app.game.models import Rarity
from app.modules.game.module import GameModule


class FixedEngine(GameEngine):
    def roll_gacha(self, seed: str | None = None) -> Rarity:
        return Rarity.B


@pytest.mark.asyncio
async def test_rare_gacha_without_owner_is_refunded_and_closed(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'gacha-handler.db'}")
    await database.create_schema()

    async with database.session() as session:
        session.add_all(
            [
                User(id=7, first_name="Jugador"),
                Chat(id=-100, type="supergroup", title="Community"),
            ]
        )
        await session.flush()
        session.add(GameProfile(user_id=7, chat_id=-100, points=GACHA_COST_POINTS))
        await session.flush()

    module = GameModule(database, Settings(admin_user_id=0))
    module.gacha_service = GachaService(FixedEngine())
    module._community_chat_id = AsyncMock(return_value=-100)

    callback = SimpleNamespace(
        id="rare-no-owner",
        from_user=SimpleNamespace(id=7),
        message=SimpleNamespace(
            chat=SimpleNamespace(id=7, type="private"),
        ),
        answer=AsyncMock(),
    )
    bot = AsyncMock()

    await module.gacha_roll(callback, bot)

    callback.answer.assert_awaited_once()
    text = callback.answer.await_args.args[0]
    assert "devolvieron" in text
    bot.send_message.assert_not_awaited()

    async with database.session() as session:
        profile = await session.scalar(
            select(GameProfile).where(
                GameProfile.user_id == 7,
                GameProfile.chat_id == -100,
            )
        )
        approval = await session.scalar(select(RareDropApproval))
        roll = await session.scalar(select(GameGachaRoll))
        refund = await session.scalar(
            select(PointTransaction).where(
                PointTransaction.reference_type == "gacha_refund",
            )
        )

    assert profile is not None
    assert profile.points == GACHA_COST_POINTS
    assert approval is not None
    assert approval.status == "rejected"
    assert roll is not None
    assert roll.granted is False
    assert refund is not None
    assert refund.amount == GACHA_COST_POINTS

    await database.close()
