from __future__ import annotations

import json

from sqlalchemy import select

from app.command_center.models import BotAvatar, CafeTable, ManualMessageCommand, MoveCommand, OperationMode
from app.command_center.telegram_gateway import TelegramGateway
from app.command_center.vault_client import CardVaultClient
from app.core.time import utc_now
from app.db.card_vault_models import BotState
from app.db.database import Database


class CommandCenterService:
    """Application service behind the future PySide6 2D Casa de Comando UI."""

    def __init__(
        self,
        database: Database,
        telegram: TelegramGateway,
        vault: CardVaultClient,
    ) -> None:
        self.database = database
        self.telegram = telegram
        self.vault = vault

    async def set_mode(self, identity: str, mode: OperationMode) -> None:
        async with self.database.session() as session:
            state = await session.scalar(
                select(BotState).where(BotState.bot_identity == identity)
            )
            if state is None:
                state = BotState(bot_identity=identity, mode=mode.value)
                session.add(state)
            else:
                state.mode = mode.value
                state.updated_at = utc_now()
            await session.flush()

    async def move_bot(self, command: MoveCommand) -> BotAvatar:
        identity = command.identity
        table = command.table
        async with self.database.session() as session:
            state = await session.scalar(
                select(BotState).where(BotState.bot_identity == identity)
            )
            if state is None:
                state = BotState(bot_identity=identity, mode=OperationMode.MANUAL.value)
                session.add(state)
            state.table_key = table.key
            state.zone_key = table.zone_key
            state.chat_id = table.chat_id
            state.message_thread_id = table.message_thread_id
            state.position_x = table.x
            state.position_y = table.y
            state.status = "at_table"
            state.updated_at = utc_now()
            await session.flush()
            return BotAvatar(
                identity=identity,
                label=identity.title(),
                x=table.x,
                y=table.y,
                table_key=table.key,
                mode=OperationMode(state.mode),
                status=state.status,
            )

    async def send_manual(self, command: ManualMessageCommand):
        await self.telegram.typing(command.identity, command.chat_id)
        return await self.telegram.send_temporary(command)

    async def card_inventory(self, user_id: int) -> list[dict]:
        return await self.vault.inventory("user", str(user_id))

    async def snapshot(self) -> list[BotAvatar]:
        async with self.database.session() as session:
            rows = list(await session.scalars(select(BotState).order_by(BotState.bot_identity)))
        return [
            BotAvatar(
                identity=row.bot_identity,
                label=row.bot_identity.title(),
                x=row.position_x,
                y=row.position_y,
                table_key=row.table_key,
                mode=OperationMode(row.mode),
                status=row.status,
            )
            for row in rows
        ]

    async def update_state_payload(self, identity: str, payload: dict) -> None:
        async with self.database.session() as session:
            state = await session.scalar(
                select(BotState).where(BotState.bot_identity == identity)
            )
            if state is None:
                state = BotState(bot_identity=identity)
                session.add(state)
            state.state_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            state.updated_at = utc_now()
            await session.flush()
