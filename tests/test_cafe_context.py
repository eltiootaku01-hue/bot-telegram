from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.core.identity import BotIdentity
from app.db.database import Database
from app.db.models import FanRequest, GameEncounter, UserChat
from app.db.trivia_models import TriviaRound
from app.services.cafe_context import CafeContextService


@pytest.fixture
async def database():
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    yield database
    await database.close()


def test_choose_is_deterministic_for_the_same_snapshot():
    service = CafeContextService()
    snapshot = service.__class__.__annotations__  # type: ignore[attr-defined]
    assert snapshot


def test_choose_prefers_live_game_state():
    service = CafeContextService()
    from app.services.cafe_context import CafeContextSnapshot

    live = CafeContextSnapshot(
        chat_id=-100,
        active_encounter=True,
        active_trivia=True,
        pending_requests=4,
        recent_new_members=2,
        recent_human_activity=True,
        observed_at=datetime(2026, 9, 20, 12, 0),
    )

    moment = service.choose(live, local_hour=12)

    assert moment.speaker is BotIdentity.SUNNA
    assert moment.key == "context-active-waifumon"


def test_choose_uses_pending_requests_when_no_game_is_active():
    service = CafeContextService()
    from app.services.cafe_context import CafeContextSnapshot

    snapshot = CafeContextSnapshot(
        chat_id=-100,
        active_encounter=False,
        active_trivia=False,
        pending_requests=1,
        recent_new_members=0,
        recent_human_activity=False,
        observed_at=datetime(2026, 9, 20, 15, 0),
    )

    moment = service.choose(snapshot, local_hour=15)

    assert moment.speaker is BotIdentity.CAMI
    assert moment.reason == "pending_fan_requests"


@pytest.mark.asyncio
async def test_snapshot_reads_live_cafe_state(database):
    service = CafeContextService()
    now = datetime(2026, 9, 20, 15, 0)

    async with database.session() as session:
        session.add_all(
            [
                GameEncounter(
                    id="ctx-game",
                    chat_id=-100,
                    character_id="asuna",
                    rarity="D",
                    answer="asuna",
                    expires_at=now + timedelta(minutes=5),
                    status="active",
                ),
                TriviaRound(
                    chat_id=-100,
                    question="Q",
                    options='["a","b"]',
                    answer_index=0,
                    explanation="",
                    points=10,
                    status="active",
                    expires_at=now + timedelta(minutes=5),
                ),
            ]
        )

    async with database.session() as session:
        snapshot = await service.snapshot(session, chat_id=-100, now=now)

    assert snapshot.active_encounter is True
    assert snapshot.active_trivia is True


@pytest.mark.asyncio
async def test_snapshot_counts_pending_requests_and_recent_members(database):
    service = CafeContextService()
    now = datetime(2026, 9, 20, 15, 0)

    async with database.session() as session:
        session.add_all(
            [
                FanRequest(
                    user_id=1,
                    chat_id=-100,
                    description="pedido 1",
                    status="pending_admin",
                    points_cost=20,
                    source_message_id=1,
                ),
                FanRequest(
                    user_id=2,
                    chat_id=-100,
                    description="pedido 2",
                    status="processing",
                    points_cost=20,
                    source_message_id=2,
                ),
                UserChat(
                    user_id=1,
                    chat_id=-100,
                    joined_at=now - timedelta(hours=2),
                    last_seen_at=now,
                ),
            ]
        )

    async with database.session() as session:
        snapshot = await service.snapshot(session, chat_id=-100, now=now)

    assert snapshot.pending_requests == 2
    assert snapshot.recent_new_members == 1


@pytest.mark.asyncio
async def test_contextual_surface_uses_authored_service_without_llm(database):
    from types import SimpleNamespace

    from app.modules.cafe.module import CafeModule

    module = CafeModule(database)
    module.context = CafeContextService()

    answers = []

    async def answer(text, **kwargs):
        answers.append(text)

    message = SimpleNamespace(
        chat=SimpleNamespace(id=-100, type="supergroup"),
        from_user=SimpleNamespace(id=7),
        answer=answer,
    )

    await module.context_command(message)

    assert answers
    assert "Momento contextual del Café" in answers[0]
    assert "canon" in answers[0]
