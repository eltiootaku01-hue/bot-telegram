from types import SimpleNamespace

import pytest

from app.db.database import Database
from app.db.models import Chat, FanRequest, User
from app.modules.requests.module import RequestModule


@pytest.mark.asyncio
async def test_my_requests_shows_only_requester_history(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'request-module.db'}")
    await database.create_schema()
    module = RequestModule(database)

    async with database.session() as session:
        session.add_all(
            [
                User(id=7, first_name="Requester"),
                User(id=8, first_name="Other"),
                Chat(id=-100, type="supergroup", title="Community"),
            ]
        )
        await session.flush()
        session.add_all(
            [
                FanRequest(
                    user_id=7,
                    chat_id=-100,
                    description="Asuna con vestido",
                    points_cost=50,
                    status="pending_admin",
                ),
                FanRequest(
                    user_id=8,
                    chat_id=-100,
                    description="Invisible para el requester",
                    points_cost=50,
                    status="completed",
                ),
            ]
        )

    answers: list[str] = []

    async def answer(text: str) -> None:
        answers.append(text)

    message = SimpleNamespace(
        chat=SimpleNamespace(type="private", id=7),
        from_user=SimpleNamespace(id=7),
        answer=answer,
    )

    await module.my_requests(message)

    assert answers
    assert "#1" in answers[0]
    assert "Asuna con vestido" in answers[0]
    assert "Invisible para el requester" not in answers[0]
    await database.close()
