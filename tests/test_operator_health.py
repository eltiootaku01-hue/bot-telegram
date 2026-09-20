import pytest

from app.core.identity import BotIdentity
from app.db.community_models import SetupSession
from app.db.database import Database
from app.db.models import BotPresenceState, Chat, DurableJob, DomainEvent, User, UserChat
from app.db.world_models import WorldCatalogEntry, WorldUsageStat
from app.services.operator_health import OperatorHealthService, format_operator_health


@pytest.mark.asyncio
async def test_operator_health_reports_only_aggregate_runtime_counts(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'health.db'}")
    await database.create_schema()

    async with database.session() as session:
        session.add_all(
            [
                User(id=77, first_name="Owner"),
                Chat(id=-100, type="supergroup", title="Café Otaku"),
                SetupSession(
                    user_id=77,
                    chat_id=-100,
                    bot_identity=BotIdentity.CHIE.value,
                    status="configured",
                ),
                UserChat(
                    user_id=77,
                    chat_id=-100,
                    status="member",
                ),
                DurableJob(job_type="demo", dedupe_key="pending-1", payload="{}"),
                DurableJob(
                    job_type="demo",
                    dedupe_key="processing-1",
                    payload="{}",
                    status="processing",
                ),
                DomainEvent(event_id="event-1", event_type="demo", payload="{}"),
                WorldCatalogEntry(
                    bot_identity=BotIdentity.CARI.value,
                    entry_type="place",
                    entry_key="cafe",
                    label="Café",
                    enabled=True,
                ),
                WorldUsageStat(
                    bot_identity=BotIdentity.CARI.value,
                    scope_type="world",
                    scope_id="global",
                    entry_type="action",
                    entry_key="community",
                    count=4,
                ),
                BotPresenceState(bot_identity=BotIdentity.CARI.value, status="active"),
            ]
        )

    service = OperatorHealthService()
    async with database.session() as session:
        snapshot = await service.snapshot(
            session,
            authorized_chat_ids=frozenset({-100}),
        )

    assert snapshot.configured_communities == 1
    assert snapshot.authorized_communities == 1
    assert snapshot.members_seen == 1
    assert snapshot.pending_jobs == 1
    assert snapshot.processing_jobs == 1
    assert snapshot.failed_jobs == 0
    assert snapshot.pending_events == 1
    assert snapshot.active_mysteries == 0
    assert snapshot.catalog_entries == 1
    assert snapshot.world_observations == 4
    assert snapshot.active_identities == 1

    text = format_operator_health(snapshot)
    assert "Salud de Ciudad Animals" in text
    assert "Café" not in text
    assert "API" not in text
    assert "La revisión es de solo lectura" in text

    await database.close()


@pytest.mark.asyncio
async def test_operator_health_does_not_count_unauthorized_communities(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'health-auth.db'}")
    await database.create_schema()

    async with database.session() as session:
        session.add_all(
            [
                SetupSession(
                    user_id=77,
                    chat_id=-100,
                    bot_identity=BotIdentity.CHIE.value,
                    status="configured",
                ),
                SetupSession(
                    user_id=78,
                    chat_id=-200,
                    bot_identity=BotIdentity.CHIE.value,
                    status="configured",
                ),
            ]
        )

    async with database.session() as session:
        snapshot = await OperatorHealthService().snapshot(
            session,
            authorized_chat_ids=frozenset({-100}),
        )

    assert snapshot.configured_communities == 2
    assert snapshot.authorized_communities == 1

    await database.close()
