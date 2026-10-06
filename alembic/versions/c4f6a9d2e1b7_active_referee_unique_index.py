# -*- coding: utf-8 -*-
"""protect active referee ownership with a partial unique index."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4f6a9d2e1b7"
down_revision: Union[str, None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
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
        "uq_active_matches_active_referee_name",
        "active_matches",
        ["referee_name"],
        unique=True,
        sqlite_where=sa.text("status IN ('WAITING', 'IN_PROGRESS')"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_active_matches_active_referee_name",
        table_name="active_matches",
    )
