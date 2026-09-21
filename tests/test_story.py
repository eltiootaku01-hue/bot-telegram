import pytest
from sqlalchemy import select

from app.core.identity import BotIdentity
from app.db.database import Database
from app.db.models import StoryProgress
from app.game.story import STORY_ARC_KEY, STORY_CHAPTERS, StoryService


def test_story_arc_has_six_noncanonical_chapters_with_character_roles() -> None:
    assert len(STORY_CHAPTERS) == 6
    assert [chapter.number for chapter in STORY_CHAPTERS] == list(range(1, 7))
    assert len({chapter.key for chapter in STORY_CHAPTERS}) == len(STORY_CHAPTERS)

    for chapter in STORY_CHAPTERS:
        assert chapter.title
        assert chapter.scene
        assert chapter.characters
        assert all(identity in set(BotIdentity) for identity in chapter.characters)
        assert chapter.gameplay_hook


@pytest.mark.asyncio
async def test_story_progress_starts_at_chapter_one(database_tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{database_tmp_path / 'story.db'}")
    await database.create_schema()

    async with database.session(write=True) as session:
        view = await StoryService.current(session, chat_id=-100)

    assert view.progress.arc_key == STORY_ARC_KEY
    assert view.progress.chapter == 1
    assert view.progress.completed is False
    assert view.chapter.key == "lights-on"

    async with database.session() as session:
        rows = list(await session.scalars(select(StoryProgress)))
    assert len(rows) == 1

    await database.close()


@pytest.fixture
def database_tmp_path(tmp_path):
    return tmp_path


@pytest.mark.asyncio
async def test_story_advance_rejects_stale_buttons_and_completes_exactly_once(database_tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{database_tmp_path / 'story-race.db'}")
    await database.create_schema()

    async with database.session(write=True) as session:
        first = await StoryService.current(session, chat_id=-100)
        advanced, changed = await StoryService.advance(
            session,
            chat_id=-100,
            expected_chapter=1,
        )

    assert changed is True
    assert advanced.progress.chapter == 2
    assert advanced.chapter.key == "half-finished-game"

    async with database.session(write=True) as session:
        stale, changed = await StoryService.advance(
            session,
            chat_id=-100,
            expected_chapter=1,
        )

    assert changed is False
    assert stale.progress.chapter == 2

    for expected in range(2, 6):
        async with database.session(write=True) as session:
            current, changed = await StoryService.advance(
                session,
                chat_id=-100,
                expected_chapter=expected,
            )
        assert changed is True
        assert current.progress.chapter == expected + 1

    async with database.session(write=True) as session:
        completed, changed = await StoryService.advance(
            session,
            chat_id=-100,
            expected_chapter=6,
        )

    assert changed is True
    assert completed.progress.chapter == 6
    assert completed.progress.completed is True

    async with database.session(write=True) as session:
        replay, changed = await StoryService.advance(
            session,
            chat_id=-100,
            expected_chapter=6,
        )

    assert changed is False
    assert replay.progress.chapter == 6
    assert replay.progress.completed is True

    await database.close()
