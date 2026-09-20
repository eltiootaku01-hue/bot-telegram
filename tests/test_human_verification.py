from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

from sqlalchemy import select

import pytest
from aiogram.types import ChatPermissions

from app.core.config import Settings
from app.db.database import Database
from app.db.models import HumanVerification
from app.services.human_verification import (
    HumanVerificationService,
    permissions_from_json,
    permissions_to_json,
)


@pytest.fixture
async def database(tmp_path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'verification.db'}")
    await database.create_schema()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_verification_decision_is_single_use(database: Database) -> None:
    service = HumanVerificationService()

    async with database.session() as session:
        await service.begin(
            session,
            chat_id=-100,
            user_id=7,
            prompt_message_id=12,
            default_permissions_json="{}",
        )

    async with database.session() as session:
        first = await service.decide(
            session,
            chat_id=-100,
            user_id=7,
            status="verified",
        )

    async with database.session() as session:
        second = await service.decide(
            session,
            chat_id=-100,
            user_id=7,
            status="rejected",
        )

    assert first is not None
    assert first.status == "verified"
    assert second is None


def test_permissions_round_trip_is_limited_to_member_permissions() -> None:
    permissions = ChatPermissions(
        can_send_messages=True,
        can_send_photos=True,
        can_invite_users=True,
    )

    encoded = permissions_to_json(permissions)
    decoded = permissions_from_json(encoded)

    assert decoded["can_send_messages"] is True
    assert decoded["can_send_photos"] is True
    assert "can_manage_topics" not in decoded
    assert "can_invite_users" not in decoded


@pytest.mark.asyncio
async def test_verification_no_restores_saved_permissions() -> None:
    from app.modules.chie.module import ChieModule

    class FakeBot:
        def __init__(self) -> None:
            self.restrict_chat_member = AsyncMock()
            self.get_chat = AsyncMock(
                return_value=SimpleNamespace(
                    permissions=permissions,
                )
            )

    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    module = ChieModule(
        database,
        Settings(
            authorized_chat_ids="-100",
            admin_user_id=77,
            allow_admin_private_chat=True,
        ),
    )
    permissions = ChatPermissions(can_send_messages=True, can_send_photos=True)

    async with database.session() as session:
        await module.verification.begin(
            session,
            chat_id=-100,
            user_id=7,
            prompt_message_id=12,
            default_permissions_json=permissions_to_json(permissions),
        )

    bot = FakeBot()
    callback = SimpleNamespace(
        data="chie:verify:no:7",
        from_user=SimpleNamespace(id=7),
        message=SimpleNamespace(
            chat=SimpleNamespace(id=-100, type="supergroup"),
            edit_text=AsyncMock(),
        ),
        answer=AsyncMock(),
    )

    await module.human_verification(callback, bot)

    async with database.session() as session:
        row = await session.scalar(
            select(HumanVerification).where(
                HumanVerification.chat_id == -100,
                HumanVerification.user_id == 7,
            )
        )

    assert row is not None
    assert row.status == "verified"
    bot.restrict_chat_member.assert_awaited_once()
    restored = bot.restrict_chat_member.await_args.kwargs["permissions"]
    assert restored.can_send_messages is True
    assert restored.can_send_photos is True
    await database.close()


@pytest.mark.asyncio
async def test_verification_yes_kicks_and_allows_rejoin() -> None:
    from app.modules.chie.module import ChieModule

    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    module = ChieModule(database, Settings(authorized_chat_ids="-100"))

    async with database.session() as session:
        await module.verification.begin(
            session,
            chat_id=-100,
            user_id=7,
            prompt_message_id=12,
            default_permissions_json="{}",
        )

    bot = SimpleNamespace(
        ban_chat_member=AsyncMock(),
        unban_chat_member=AsyncMock(),
    )
    callback = SimpleNamespace(
        data="chie:verify:yes:7",
        from_user=SimpleNamespace(id=7),
        message=SimpleNamespace(
            chat=SimpleNamespace(id=-100, type="supergroup"),
            edit_text=AsyncMock(),
        ),
        answer=AsyncMock(),
    )

    await module.human_verification(callback, bot)

    bot.ban_chat_member.assert_awaited_once_with(-100, 7)
    bot.unban_chat_member.assert_awaited_once_with(-100, 7)

    async with database.session() as session:
        row = await session.scalar(
            __import__("sqlalchemy", fromlist=["select"]).select(HumanVerification).where(
                HumanVerification.chat_id == -100,
                HumanVerification.user_id == 7,
            )
        )

    assert row is not None
    assert row.status == "rejected"
    await database.close()


@pytest.mark.asyncio
async def test_wrong_user_cannot_use_another_users_verification(database: Database) -> None:
    service = HumanVerificationService()
    
    async with database.session() as session:
        await service.begin(
            session,
            chat_id=-100,
            user_id=7,
            prompt_message_id=12,
            default_permissions_json="{}",
        )

    from app.modules.chie.module import ChieModule

    module = ChieModule(database, Settings(authorized_chat_ids="-100"))
    callback = SimpleNamespace(
        data="chie:verify:no:7",
        from_user=SimpleNamespace(id=8),
        message=SimpleNamespace(chat=SimpleNamespace(id=-100, type="supergroup")),
        answer=AsyncMock(),
    )

    await module.human_verification(callback, AsyncMock())

    callback.answer.assert_awaited_once()
    assert "no es para vos" in callback.answer.await_args.args[0]

    async with database.session() as session:
        row = await session.scalar(
            __import__("sqlalchemy", fromlist=["select"]).select(HumanVerification).where(
                HumanVerification.chat_id == -100,
                HumanVerification.user_id == 7,
            )
        )

    assert row is not None
    assert row.status == "pending"


@pytest.mark.asyncio
async def test_begin_honors_configured_timeout(database: Database) -> None:
    service = HumanVerificationService()
    base = datetime(2026, 9, 20, 18, 0, 0)

    async with database.session() as session:
        row = await service.begin(
            session,
            chat_id=-100,
            user_id=8,
            prompt_message_id=13,
            default_permissions_json="{}",
            timeout_seconds=45,
            now=base,
        )

    assert row.expires_at == base + timedelta(seconds=45)


@pytest.mark.asyncio
async def test_begin_rejects_unreasonably_short_timeout(database: Database) -> None:
    service = HumanVerificationService()

    async with database.session() as session:
        with pytest.raises(ValueError, match="at least 30"):
            await service.begin(
                session,
                chat_id=-100,
                user_id=9,
                prompt_message_id=14,
                default_permissions_json="{}",
                timeout_seconds=29,
            )


@pytest.mark.asyncio
async def test_verification_decision_cannot_win_after_deadline(database: Database) -> None:
    service = HumanVerificationService()
    base = datetime(2026, 9, 20, 18, 0, 0)

    async with database.session() as session:
        await service.begin(
            session,
            chat_id=-100,
            user_id=10,
            prompt_message_id=15,
            default_permissions_json="{}",
            timeout_seconds=30,
            now=base,
        )

    async with database.session() as session:
        decided = await service.decide(
            session,
            chat_id=-100,
            user_id=10,
            status="verified",
            now=base + timedelta(seconds=31),
        )

    assert decided is None

    async with database.session() as session:
        row = await session.scalar(
            select(HumanVerification).where(
                HumanVerification.chat_id == -100,
                HumanVerification.user_id == 10,
            )
        )

    assert row is not None
    assert row.status == "pending"


@pytest.mark.asyncio
async def test_recent_join_count_supports_adaptive_raid_detection(database: Database) -> None:
    service = HumanVerificationService()
    base = datetime(2026, 9, 20, 18, 0, 0)

    async with database.session() as session:
        for user_id in range(1, 6):
            await service.begin(
                session,
                chat_id=-100,
                user_id=user_id,
                prompt_message_id=user_id,
                default_permissions_json="{}",
                timeout_seconds=120,
                now=base,
            )
        count = await service.recent_join_count(
            session,
            chat_id=-100,
            window_seconds=60,
            now=base + timedelta(seconds=10),
        )
        old_count = await service.recent_join_count(
            session,
            chat_id=-100,
            window_seconds=5,
            now=base + timedelta(seconds=10),
        )

    assert count == 5
    assert old_count == 0
