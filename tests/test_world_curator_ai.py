import pytest
from sqlalchemy import select

from app.brain.provider import LLMRequest
from app.brain.provider import LLMProviderError
from app.core.config import Settings
from app.core.identity import BotIdentity
from app.db.database import Database
from app.db.world_models import WorldProposal, WorldReview
from app.services.world_curator import WorldCuratorService
from app.services.world_curator_ai import (
    CURATOR_PERSONA,
    StoredWorldProposals,
    WorldCuratorAIService,
    format_world_proposals,
)


class FakeBrain:
    def __init__(self, payload: str) -> None:
        self.payload = payload
        self.requests: list[LLMRequest] = []

    async def generate(self, request: LLMRequest) -> str:
        self.requests.append(request)
        return self.payload


@pytest.fixture
async def database():
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_ai_curator_uses_only_review_snapshot_and_persists_pending_proposal(
    database: Database,
) -> None:
    brain = FakeBrain(
        '{"proposals":[{"title":"Más juegos","idea":"Agregar una escena authored de juego.","reason":"WaifuMon aparece en el snapshot.","affected_identities":["sunna"]}]}'
    )
    service = WorldCuratorAIService(
        Settings(ai_enabled=True, ai_enabled_chie=True, ollama_model="test-model"),
        brain=brain,  # type: ignore[arg-type]
    )
    world = WorldCuratorService()

    async with database.session() as session:
        report = await world.build_daily(session, day_key="2026-09-20")
        review = await session.scalar(
            select(WorldReview).where(WorldReview.period_key == "2026-09-20")
        )
        assert review is not None

        stored = await service.propose(
            session,
            review_row=review,
            report=report,
        )

    assert stored.status == "pending"
    assert len(stored.items) == 1
    assert stored.items[0].affected_identities == (BotIdentity.SUNNA,)
    assert brain.requests
    assert brain.requests[0].persona == CURATOR_PERSONA
    assert "cami.media.publish" in brain.requests[0].system_extra
    assert "sunna.waifumon.capture" in brain.requests[0].system_extra
    assert "No inventes process ids" in brain.requests[0].system_extra
    assert "No hables como personaje" in brain.requests[0].persona
    assert "user_text" not in brain.requests[0].user_text
    assert "conversation" not in brain.requests[0].user_text

    async with database.session() as session:
        rows = list(await session.scalars(select(WorldProposal)))

    assert len(rows) == 1
    assert rows[0].status == "pending"


@pytest.mark.asyncio
async def test_ai_curator_reuses_existing_proposal_without_second_llm_call(database: Database) -> None:
    brain = FakeBrain(
        '{"proposals":[{"title":"Idea","idea":"Una escena pequeña.","reason":"Hay espacio.","affected_identities":[] }]}'
    )
    settings = Settings(ai_enabled=True, ai_enabled_chie=True, ollama_model="test-model")
    service = WorldCuratorAIService(settings, brain=brain)  # type: ignore[arg-type]
    world = WorldCuratorService()

    async with database.session() as session:
        report = await world.build_daily(session, day_key="2026-09-20")
        review = await session.scalar(select(WorldReview))
        assert review is not None
        first = await service.propose(session, review_row=review, report=report)

    async with database.session() as session:
        review = await session.scalar(select(WorldReview))
        assert review is not None
        second = await service.propose(session, review_row=review, report=report)

    assert first == second
    assert len(brain.requests) == 1


def test_ai_curator_rejects_unknown_identity_and_wrong_shape() -> None:
    with pytest.raises(LLMProviderError):
        WorldCuratorAIService._parse(
            '{"proposals":[{"title":"x","idea":"y","reason":"z","affected_identities":["unknown"]}]}'
        )

    with pytest.raises(LLMProviderError):
        WorldCuratorAIService._parse('{"proposals":[]}')


def test_ai_curator_formats_untrusted_human_review_text() -> None:
    brain = FakeBrain(
        '{"proposals":[{"title":"Revisar","idea":"Crear dos escenas.","reason":"Hay pocas escenas de interacción.","affected_identities":["cari","cami"]}]}'
    )
    # The parser itself is deterministic and independent from provider I/O.
    service = WorldCuratorAIService(
        Settings(ai_enabled=True, ai_enabled_chie=True),
        brain=brain,  # type: ignore[arg-type]
    )
    stored = service._parse(brain.payload)
    rendered = format_world_proposals(
        StoredWorldProposals(
            proposal_id=1,
            review_id=1,
            generator="brain:ollama:test",
            status="pending",
            items=stored,
        )
    )
    assert "no confiables" in rendered
    assert "Cari, Cami" in rendered


@pytest.mark.asyncio
async def test_ai_curator_decision_is_single_use(database: Database) -> None:
    brain = FakeBrain(
        '{"proposals":[{"title":"Idea","idea":"Una escena pequeña.","reason":"Hay espacio.","affected_identities":[] }]}'
    )
    settings = Settings(ai_enabled=True, ai_enabled_chie=True, ollama_model="test-model")
    service = WorldCuratorAIService(settings, brain=brain)
    world = WorldCuratorService()

    async with database.session() as session:
        report = await world.build_daily(session, day_key="2026-09-21")
        review = await session.scalar(select(WorldReview))
        assert review is not None
        stored = await service.propose(session, review_row=review, report=report)
        first = await service.decide(session, proposal_id=stored.proposal_id, approved=True)
        second = await service.decide(session, proposal_id=stored.proposal_id, approved=False)

    assert first is True
    assert second is False

    async with database.session() as session:
        row = await session.get(WorldProposal, stored.proposal_id)

    assert row is not None
    assert row.status == "accepted"


@pytest.mark.asyncio
async def test_ai_curator_database_path_reuses_persisted_proposal(database: Database) -> None:
    brain = FakeBrain(
        '{"proposals":[{"title":"Idea","idea":"Una escena pequeña.","reason":"Hay datos.","affected_identities":["cari"]}]}'
    )
    settings = Settings(
        ai_enabled=True,
        ai_enabled_chie=True,
        ollama_model="test-model",
    )
    service = WorldCuratorAIService(settings, brain=brain)  # type: ignore[arg-type]
    world = WorldCuratorService()

    async with database.session() as session:
        report = await world.build_daily(session, day_key="2026-09-22")
        review = await session.scalar(select(WorldReview))
        assert review is not None
        review_id = review.id

    first = await service.propose_for_database(
        database,
        review_id=review_id,
        report=report,
    )
    second = await service.propose_for_database(
        database,
        review_id=review_id,
        report=report,
    )

    assert first == second
    assert len(brain.requests) == 1


@pytest.mark.asyncio
async def test_ai_curator_database_path_keeps_llm_outside_active_db_transaction(
    database: Database,
) -> None:
    class TransactionProbeBrain(FakeBrain):
        async def generate(self, request: LLMRequest) -> str:
            async with database.session() as session:
                await session.execute(select(WorldReview.id).limit(1))
            return await super().generate(request)

    brain = TransactionProbeBrain(
        '{"proposals":[{"title":"Idea","idea":"Una escena.","reason":"Probe.","affected_identities":[]}]}' 
    )
    settings = Settings(
        ai_enabled=True,
        ai_enabled_chie=True,
        ollama_model="test-model",
    )
    service = WorldCuratorAIService(settings, brain=brain)  # type: ignore[arg-type]
    world = WorldCuratorService()

    async with database.session() as session:
        report = await world.build_daily(session, day_key="2026-09-23")
        review = await session.scalar(select(WorldReview))
        assert review is not None
        review_id = review.id

    stored = await service.propose_for_database(
        database,
        review_id=review_id,
        report=report,
    )

    assert stored.status == "pending"
