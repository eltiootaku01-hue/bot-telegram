"""add duel slots and card lock state

Revision ID: a1b2c3d4e5f6
Revises: None
Create Date: 2026-09-26 05:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite no permite alterar algunas restricciones/FK directamente.
    # batch_alter_table reconstruye la tabla de forma segura.
    with op.batch_alter_table("card_instances", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_locked",
                sa.Boolean(),
                server_default=sa.text("0"),
                nullable=False,
            )
        )
        batch_op.create_index(
            "ix_card_instances_is_locked",
            ["is_locked"],
            unique=False,
        )

    with op.batch_alter_table("active_matches", schema=None) as batch_op:
        # Slots de mazo: UUIDs de CardInstance.
        batch_op.add_column(
            sa.Column("p1_waifu_instance_id", sa.String(length=36), nullable=True)
        )
        batch_op.add_column(
            sa.Column("p1_equip_instance_id", sa.String(length=36), nullable=True)
        )
        batch_op.add_column(
            sa.Column("p1_magic_instance_id", sa.String(length=36), nullable=True)
        )
        batch_op.add_column(
            sa.Column("p2_waifu_instance_id", sa.String(length=36), nullable=True)
        )
        batch_op.add_column(
            sa.Column("p2_equip_instance_id", sa.String(length=36), nullable=True)
        )
        batch_op.add_column(
            sa.Column("p2_magic_instance_id", sa.String(length=36), nullable=True)
        )

        # Estado de apuestas.
        batch_op.add_column(
            sa.Column("staked_rarity", sa.String(length=10), nullable=True)
        )
        batch_op.add_column(
            sa.Column("p1_staked_card_id", sa.String(length=36), nullable=True)
        )
        batch_op.add_column(
            sa.Column("p2_staked_card_id", sa.String(length=36), nullable=True)
        )

        # Moneda e iniciativa.
        batch_op.add_column(
            sa.Column("coin_picker_id", sa.BigInteger(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("coin_choice", sa.String(length=10), nullable=True)
        )
        batch_op.add_column(
            sa.Column("first_turn_player_id", sa.BigInteger(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("current_turn_player_id", sa.BigInteger(), nullable=True)
        )

        # Referencias UUID a CardInstance.
        batch_op.create_foreign_key(
            "fk_active_matches_p1_waifu",
            "card_instances",
            ["p1_waifu_instance_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_active_matches_p1_equip",
            "card_instances",
            ["p1_equip_instance_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_active_matches_p1_magic",
            "card_instances",
            ["p1_magic_instance_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_active_matches_p2_waifu",
            "card_instances",
            ["p2_waifu_instance_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_active_matches_p2_equip",
            "card_instances",
            ["p2_equip_instance_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_active_matches_p2_magic",
            "card_instances",
            ["p2_magic_instance_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_active_matches_p1_staked",
            "card_instances",
            ["p1_staked_card_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_active_matches_p2_staked",
            "card_instances",
            ["p2_staked_card_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("active_matches", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_active_matches_p2_staked",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_active_matches_p1_staked",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_active_matches_p2_magic",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_active_matches_p2_equip",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_active_matches_p2_waifu",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_active_matches_p1_magic",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_active_matches_p1_equip",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_active_matches_p1_waifu",
            type_="foreignkey",
        )

        batch_op.drop_column("current_turn_player_id")
        batch_op.drop_column("first_turn_player_id")
        batch_op.drop_column("coin_choice")
        batch_op.drop_column("coin_picker_id")
        batch_op.drop_column("p2_staked_card_id")
        batch_op.drop_column("p1_staked_card_id")
        batch_op.drop_column("staked_rarity")
        batch_op.drop_column("p2_magic_instance_id")
        batch_op.drop_column("p2_equip_instance_id")
        batch_op.drop_column("p2_waifu_instance_id")
        batch_op.drop_column("p1_magic_instance_id")
        batch_op.drop_column("p1_equip_instance_id")
        batch_op.drop_column("p1_waifu_instance_id")

    with op.batch_alter_table("card_instances", schema=None) as batch_op:
        batch_op.drop_index("ix_card_instances_is_locked")
        batch_op.drop_column("is_locked")
