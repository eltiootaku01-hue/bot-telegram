# -*- coding: utf-8 -*-
"""protect active referee ownership with a partial unique index."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4f6a9d2e1b7"
down_revision: Union[str, None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEX_NAME = "uq_active_matches_active_referee_name"
_TABLE_NAME = "active_matches"
_COLUMN_NAME = "referee_name"
_EXPECTED_SQL = (
    "CREATE UNIQUE INDEX "
    "uq_active_matches_active_referee_name "
    "ON active_matches (referee_name) "
    "WHERE status IN ('WAITING', 'IN_PROGRESS')"
)


def _normalize_sql(value: str) -> str:
    return " ".join(value.replace('"', "").split()).casefold()


def _existing_index(connection):
    return connection.exec_driver_sql(
        """
        SELECT tbl_name, sql
        FROM sqlite_master
        WHERE type = 'index'
          AND name = ?
        """,
        (_INDEX_NAME,),
    ).fetchone()


def _index_matches_expected(connection, index_sql: str | None) -> bool:
    if index_sql is None:
        return False
    index_rows = connection.exec_driver_sql(
        "PRAGMA index_list('active_matches')"
    ).fetchall()
    target_rows = [
        row for row in index_rows if row[1] == _INDEX_NAME
    ]
    if len(target_rows) != 1:
        return False
    target = target_rows[0]
    if int(target[2]) != 1:
        return False
    if len(target) < 5 or int(target[4]) != 1:
        return False

    columns = connection.exec_driver_sql(
        "PRAGMA index_info('uq_active_matches_active_referee_name')"
    ).fetchall()
    if [row[2] for row in columns] != [_COLUMN_NAME]:
        return False

    return _normalize_sql(index_sql) == _normalize_sql(_EXPECTED_SQL)


def upgrade() -> None:
    connection = op.get_bind()
    existing = _existing_index(connection)
    if existing is not None:
        table_name, index_sql = existing
        if table_name != _TABLE_NAME or not _index_matches_expected(
            connection,
            index_sql,
        ):
            raise RuntimeError(
                "Existing index "
                f"{_INDEX_NAME!r} has an incompatible definition; "
                "refusing to replace it."
            )
        return

    duplicates = connection.execute(
        sa.text(
            """
            SELECT referee_name, COUNT(*)
            FROM active_matches
            WHERE status IN ('WAITING', 'IN_PROGRESS')
            GROUP BY referee_name
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()
    if duplicates:
        names = ", ".join(str(row[0]) for row in duplicates)
        raise RuntimeError(
            "Cannot create active referee ownership constraint; "
            f"duplicate active referees detected: {names}"
        )
    op.create_index(
        _INDEX_NAME,
        _TABLE_NAME,
        [_COLUMN_NAME],
        unique=True,
        sqlite_where=sa.text("status IN ('WAITING', 'IN_PROGRESS')"),
    )


def downgrade() -> None:
    # SQLite/Alembic cannot persist whether this index was pre-created by
    # Base.metadata.create_all() or created by this migration. The downgrade
    # therefore removes the named index unconditionally; a later create_all()
    # can recreate the ORM-defined index.
    op.drop_index(
        _INDEX_NAME,
        table_name=_TABLE_NAME,
    )
