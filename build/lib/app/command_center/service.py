from __future__ import annotations

import json

from sqlalchemy import select

from app.command_center.models import BotAvatar, ManualMessageCommand, MoveCommand, OperationMode
from app.command_center.telegram_gateway import TelegramGateway
from app.command_center.vault_client import CardVaultClient
from app.core.config import get_settings
from app.core.time import utc_now
from app.db.card_vault_models import BotState
from app.db.database import Database
from app.dialogues.models import DialogueEvent
from app.dialogues.renderer import DialogueRenderer
from app.dialogues.store import DialogueStore


class CommandCenterService:
    """Application service behind the future PySide6 2D Casa de Comando UI."""

    def __init__(
        self,
        database: Database,
        telegram: TelegramGateway,
        vault: CardVaultClient,
        dialogues: DialogueStore | None = None,
    ) -> None:
        self.database = database
        self.telegram = telegram
        self.vault = vault
        self.dialogues = dialogues or DialogueStore(get_settings().dialogues_path)
        self.dialogue_renderer = DialogueRenderer(self.dialogues)

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

    def render_dialogue(
        self,
        event: DialogueEvent | str,
        identity: str,
        variables: dict[str, object] | None = None,
    ) -> str:
        """Render one offline phrase for the manual operator UI."""
        return self.dialogue_renderer.render(event, identity, variables or {})

    def add_dialogue(self, event: DialogueEvent | str, identity: str, text: str) -> None:
        """Append an authored phrase; file replacement is atomic."""
        self.dialogues.upsert(event, identity, text)

    def edit_dialogue(
        self,
        event: DialogueEvent | str,
        identity: str,
        index: int,
        text: str,
    ) -> None:
        self.dialogues.replace(event, identity, index, text)

    def delete_dialogue(self, event: DialogueEvent | str, identity: str, index: int) -> None:
        self.dialogues.remove(event, identity, index)

    def dialogue_catalog(self) -> dict[str, dict[str, tuple[str, ...]]]:
        return dict(self.dialogues.export())

    async def send_dialogue(
        self,
        *,
        event: DialogueEvent | str,
        identity: str,
        chat_id: int,
        message_thread_id: int | None = None,
        variables: dict[str, object] | None = None,
        temporary: bool = True,
    ):
        text = self.render_dialogue(event, identity, variables)
        command = ManualMessageCommand(
            identity=identity,
            chat_id=chat_id,
            message_thread_id=message_thread_id,
            text=text,
        )
        await self.telegram.typing(identity, chat_id)
        return await (
            self.telegram.send_temporary(command)
            if temporary
            else self.telegram.send_text(command)
        )

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
