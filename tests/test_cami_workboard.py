from datetime import datetime, timedelta

import pytest

from app.db.database import Database
from app.db.models import FanRequest, MediaAsset, RequestStatus, User
from app.services.cami_workboard import CamiWorkboardService, format_cami_workboard


@pytest.fixture
async def database(tmp_path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'cami-workboard.db'}")
    await database.create_schema()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_workboard_prioritizes_ambiguous_delivery_and_overdue_requests(database):
    service = CamiWorkboardService()
    now = datetime(2026, 9, 20, 15, 0, 0)

    async with database.session() as session:
        session.add_all(
            [
                User(id=7, first_name="Operator"),
                FanRequest(
                    user_id=7,
                    chat_id=-100,
                    description="Pedido vencido",
                    status=RequestStatus.PENDING_ADMIN.value,
                    points_cost=50,
                    due_at=now - timedelta(minutes=1),
                ),
                FanRequest(
                    user_id=7,
                    chat_id=-100,
                    description="Pedido normal",
                    status=RequestStatus.PENDING_ADMIN.value,
                    points_cost=50,
                    due_at=now + timedelta(hours=1),
                ),
                MediaAsset(
                    telegram_file_id="ambiguous",
                    source_chat_id=7,
                    source_message_id=1,
                    status="delivery_unknown",
                    character_id="asuna",
                    anime="Sword Art Online",
                ),
                MediaAsset(
                    telegram_file_id="inbox",
                    source_chat_id=7,
                    source_message_id=2,
                    status="cami_inbox",
                ),
            ]
        )

    async with database.session() as session:
        items = await service.next_items(session, limit=4, now=now)

    assert [item.kind for item in items[:2]] == ["media", "request"]
    assert items[0].priority > items[1].priority
    assert items[1].overdue is True
    assert items[0].next_action.startswith("Resolver la entrega")
    assert items[-1].title == "Pedido #2" or items[-1].title == "Material #4"


@pytest.mark.asyncio
async def test_workboard_is_bounded_and_stable(database):
    service = CamiWorkboardService()
    now = datetime(2026, 9, 20, 15, 0, 0)

    async with database.session() as session:
        for index in range(20):
            session.add(
                MediaAsset(
                    telegram_file_id=f"asset-{index}",
                    source_chat_id=7,
                    source_message_id=index + 1,
                    status="needs_tag",
                    created_at=now + timedelta(seconds=index),
                )
            )

    async with database.session() as session:
        first = await service.next_items(session, limit=5, now=now)
        second = await service.next_items(session, limit=5, now=now)

    assert len(first) == 5
    assert first == second
    assert [item.reference_id for item in first] == sorted(item.reference_id for item in first)


def test_workboard_format_marks_overdue_items():
    from app.services.cami_workboard import CamiWorkItem

    item = CamiWorkItem(
        kind="request",
        reference_id=1,
        priority=1200,
        title="Pedido #1",
        detail="Pedido urgente",
        next_action="Atender de inmediato",
        overdue=True,
    )

    text = format_cami_workboard([item])

    assert "TABLERO" in text.upper()
    assert "SLA VENCIDO" in text
    assert "Atender de inmediato" in text
