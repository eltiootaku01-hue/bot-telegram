from datetime import datetime

import pytest

from app.core.config import Settings
from app.core.identity import BotIdentity
from app.db.community_models import SetupSession
from app.db.database import Database
from app.db.models import Chat, User, UserChat
from app.services.community import CommunityResolver


@pytest.mark.asyncio
async def test_private_user_resolves_to_recent_configured_membership(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'community.db'}")
    await database.create_schema()

    async with database.session() as session:
        session.add(User(id=7, first_name="User"))
        session.add_all(
            [
                Chat(id=-100, type="supergroup", title="One"),
                Chat(id=-200, type="supergroup", title="Two"),
            ]
        )
        session.add_all(
            [
                SetupSession(
                    user_id=1,
                    chat_id=-100,
                    bot_identity=BotIdentity.CHIE.value,
                    status="configured",
                ),
                SetupSession(
                    user_id=2,
                    chat_id=-200,
                    bot_identity=BotIdentity.CHIE.value,
                    status="configured",
                ),
            ]
        )
        await session.flush()
        session.add_all(
            [
                UserChat(
                    user_id=7,
                    chat_id=-100,
                    status="member",
                    last_seen_at=datetime(2026, 9, 19, 10, 0, 0),
                ),
                UserChat(
                    user_id=7,
                    chat_id=-200,
                    status="creator",
                    last_seen_at=datetime(2026, 9, 19, 11, 0, 0),
                ),
            ]
        )

    async with database.session() as session:
        resolved = await CommunityResolver(Settings(authorized_chat_ids='-100,-200')).for_user(session, 7)

    assert resolved == -200
    await database.close()


@pytest.mark.asyncio
async def test_private_user_gets_single_configured_community_without_membership(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'single.db'}")
    await database.create_schema()

    async with database.session() as session:
        session.add(
            SetupSession(
                user_id=1,
                chat_id=-100,
                bot_identity="chie",
                status="configured",
            )
        )

    async with database.session() as session:
        resolved = await CommunityResolver().for_user(session, 7)

    assert resolved == -100
    await database.close()


@pytest.mark.asyncio
async def test_private_user_gets_no_community_when_multiple_exist_and_no_membership(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'multiple.db'}")
    await database.create_schema()

    async with database.session() as session:
        session.add_all(
            [
                SetupSession(
                    user_id=1,
                    chat_id=-100,
                    bot_identity="chie",
                    status="configured",
                ),
                SetupSession(
                    user_id=2,
                    chat_id=-200,
                    bot_identity="chie",
                    status="configured",
                ),
            ]
        )

    async with database.session() as session:
        resolved = await CommunityResolver().for_user(session, 7)

    assert resolved is None
    await database.close()


@pytest.mark.asyncio
async def test_configured_returns_unique_communities(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'configured.db'}")
    await database.create_schema()

    async with database.session() as session:
        session.add_all(
            [
                SetupSession(user_id=1, chat_id=-100, bot_identity="chie", status="configured"),
                SetupSession(user_id=2, chat_id=-100, bot_identity="chie", status="configured"),
                SetupSession(user_id=3, chat_id=-200, bot_identity="chie", status="configured"),
            ]
        )

    async with database.session() as session:
        rows = await CommunityResolver(Settings(authorized_chat_ids='-100,-200')).configured(session)

    assert rows == [-100, -200]
    await database.close()


@pytest.mark.asyncio
async def test_private_user_ignores_configured_community_removed_from_allowlist(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'revoked.db'}")
    await database.create_schema()

    async with database.session() as session:
        session.add_all(
            [
                SetupSession(
                    user_id=1,
                    chat_id=-100,
                    bot_identity="chie",
                    status="configured",
                ),
                SetupSession(
                    user_id=2,
                    chat_id=-200,
                    bot_identity="chie",
                    status="configured",
                ),
            ]
        )

    async with database.session() as session:
        resolved = await CommunityResolver(
            Settings(authorized_chat_ids="-200")
        ).for_user(session, 7)

    assert resolved is None

    async with database.session() as session:
        rows = await CommunityResolver(
            Settings(authorized_chat_ids="-200")
        ).configured(session)

    assert rows == [-200]
    await database.close()
