from sqlalchemy import inspect, text
import pytest

from app.db.database import Database


@pytest.mark.asyncio
async def test_schema_removes_legacy_evolution_stage_column(tmp_path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'waifumon.db'}")
    await database.create_schema()

    async with database.engine.begin() as connection:
        await connection.execute(
            text(
                "ALTER TABLE game_collection "
                "ADD COLUMN evolution_stage INTEGER NOT NULL DEFAULT 4"
            )
        )

    await database.create_schema()

    async with database.engine.begin() as connection:
        columns = {
            column["name"]
            for column in inspect(connection).get_columns("game_collection")
        }
        table_sql = (
            await connection.execute(
                text(
                    "SELECT sql FROM sqlite_master "
                    "WHERE type='table' AND name='game_collection'"
                )
            )
        ).scalar_one()

    assert "evolution_stage" not in columns
    assert "level <= 30" in table_sql

    await database.close()
