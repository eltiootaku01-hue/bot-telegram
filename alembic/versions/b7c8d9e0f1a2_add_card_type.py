# -*- coding: utf-8 -*-
"""add card type to cards

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-09-26 23:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite necesita reconstruir la tabla para agregar una columna NOT NULL
    # de forma compatible con datos existentes.
    with op.batch_alter_table("cards", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "card_type",
                sa.String(length=20),
                nullable=False,
                server_default="WAIFU",
            )
        )

    # El valor por defecto solo es necesario durante la migración de filas
    # existentes; el modelo SQLAlchemy proporciona el valor por defecto para
    # nuevas entidades.
    with op.batch_alter_table("cards", schema=None) as batch_op:
        batch_op.alter_column(
            "card_type",
            server_default=None,
        )


def downgrade() -> None:
    with op.batch_alter_table("cards", schema=None) as batch_op:
        batch_op.drop_column("card_type")
