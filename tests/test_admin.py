from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.db.database import Database
from app.db.models import Chat, GameCollection, GameGachaRoll, GameProfile, RareDropApproval, User
from app.game.models import Rarity
from app.modules.admin.module import AdminModule


def test_rare_approval_owner_requires_private_owner_chat() -> None:
    module = AdminModule(
        Database("sqlite+aiosqlite:///:memory:"),
        Settings(admin_user_id=77),
    )

    owner = SimpleNamespace(id=77)
    private_message = SimpleNamespace(
        chat=SimpleNamespace(type="private", id=77),
    )
    group_message = SimpleNamespace(
        chat=SimpleNamespace(type="supergroup", id=-100),
    )
    private_callback = SimpleNamespace(from_user=owner, message=private_message)
    group_callback = SimpleNamespace(from_user=owner, message=group_message)

    assert module._is_owner(private_callback) is True
    assert module._is_owner(group_callback) is False


@pytest.mark.asyncio
async def test_rare_approval_notifies_player_after_approval() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()

    async with database.session() as session:
        session.add_all(
            [
                User(id=7, first_name="Jugador"),
                Chat(id=-100, type="supergroup", title="Community"),
                GameProfile(user_id=7, chat_id=-100, points=10),
                RareDropApproval(
                    id=1,
                    character_id="taiga",
                    rarity=Rarity.B.value,
                    target_user_id=7,
                    target_chat_id=-100,
                    status="pending",
                ),
                GameGachaRoll(
                    id=1,
                    roll_id="approval-roll",
                    user_id=7,
                    chat_id=-100,
                    rolled_rarity=Rarity.B.value,
                    character_id="taiga",
                    approval_id=1,
                    granted=False,
                ),
            ]
        )

    bot = AsyncMock()
    module = AdminModule(database, Settings(admin_user_id=77))

    callback = SimpleNamespace(
        from_user=SimpleNamespace(id=77),
        message=SimpleNamespace(
            chat=SimpleNamespace(type="private", id=77),
            edit_text=AsyncMock(),
        ),
        data="admin:rare:approve:1",
        answer=AsyncMock(),
    )

    await module.rare_decision(callback, bot)

    bot.send_message.assert_awaited_once()
    args = bot.send_message.await_args.args
    assert args[0] == 7
    assert "drop raro fue aprobado" in args[1]
    assert "Taiga" in args[1]

    async with database.session() as session:
        approval = await session.get(RareDropApproval, 1)
        collection = await session.scalar(
            select(GameCollection).where(GameCollection.character_id == "taiga")
        )

    assert approval is not None
    assert approval.status == "approved"
    assert collection is not None

    await database.close()
