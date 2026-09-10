from datetime import datetime

from aiogram.types import Chat as TgChat, User as TgUser
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chat, GameProfile, PointTransaction, User, UserChat


class MemberRepository:
    """Persists Telegram identity, membership and activity without involving the AI."""

    async def touch(self, session: AsyncSession, user: TgUser, chat: TgChat) -> None:
        now = datetime.utcnow()
        db_user = await session.get(User, user.id)
        if db_user is None:
            db_user = User(
                id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                language_code=user.language_code,
                is_bot=user.is_bot,
                created_at=now,
                last_seen_at=now,
            )
            session.add(db_user)
        else:
            db_user.username = user.username
            db_user.first_name = user.first_name
            db_user.last_name = user.last_name
            db_user.language_code = user.language_code
            db_user.is_bot = user.is_bot
            db_user.last_seen_at = now

        db_chat = await session.get(Chat, chat.id)
        if db_chat is None:
            db_chat = Chat(
                id=chat.id,
                type=chat.type,
                title=chat.title,
                username=chat.username,
                created_at=now,
                last_seen_at=now,
            )
            session.add(db_chat)
        else:
            db_chat.type = chat.type
            db_chat.title = chat.title
            db_chat.username = chat.username
            db_chat.last_seen_at = now

        link = await session.scalar(select(UserChat).where(UserChat.user_id == user.id, UserChat.chat_id == chat.id))
        if link is None:
            session.add(UserChat(
                user_id=user.id, chat_id=chat.id, status="member", message_count=1,
                first_seen_at=now, joined_at=now, last_seen_at=now,
            ))
        else:
            link.message_count += 1
            link.last_seen_at = now
            if link.status in {"left", "kicked"}:
                link.status = "member"
                link.joined_at = link.joined_at or now
                link.left_at = None
        await session.commit()

    async def set_membership(self, session: AsyncSession, user: TgUser, chat: TgChat, status: str) -> None:
        now = datetime.utcnow()
        await self._ensure_user(session, user, now)
        await self._ensure_chat(session, chat, now)
        link = await session.scalar(select(UserChat).where(UserChat.user_id == user.id, UserChat.chat_id == chat.id))
        if link is None:
            link = UserChat(user_id=user.id, chat_id=chat.id, first_seen_at=now)
            session.add(link)
        link.status = status
        link.last_seen_at = now
        if status in {"member", "administrator", "creator"}:
            link.joined_at = link.joined_at or now
            link.left_at = None
        elif status in {"left", "kicked"}:
            link.left_at = now
        await session.commit()

    async def get_or_create_game_profile(
        self, session: AsyncSession, user_id: int, chat_id: int, *, commit: bool = True
    ) -> GameProfile:
        profile = await session.scalar(select(GameProfile).where(
            GameProfile.user_id == user_id, GameProfile.chat_id == chat_id,
        ))
        if profile is None:
            profile = GameProfile(user_id=user_id, chat_id=chat_id)
            try:
                async with session.begin_nested():
                    session.add(profile)
                    await session.flush()
            except IntegrityError:
                profile = await session.scalar(select(GameProfile).where(
                    GameProfile.user_id == user_id, GameProfile.chat_id == chat_id,
                ))
                if profile is None:
                    raise
            if commit:
                await session.commit()
                await session.refresh(profile)
        return profile

    async def add_points(
        self, session: AsyncSession, *, user_id: int, chat_id: int, amount: int,
        reason: str, reference_type: str | None = None, reference_id: str | None = None,
        commit: bool = True,
    ) -> int:
        """Atomically add points and make reference-keyed rewards idempotent."""
        if amount < 0:
            raise ValueError("Point amount must not be negative")
        profile = await self.get_or_create_game_profile(session, user_id, chat_id, commit=False)
        has_reference = reference_type is not None and reference_id is not None
        if amount:
            try:
                async with session.begin_nested():
                    await session.execute(
                        update(GameProfile)
                        .where(GameProfile.id == profile.id)
                        .values(points=GameProfile.points + amount, updated_at=datetime.utcnow())
                    )
                    session.add(PointTransaction(
                        user_id=user_id, chat_id=chat_id, amount=amount, reason=reason,
                        reference_type=reference_type, reference_id=reference_id,
                    ))
                    await session.flush()
            except IntegrityError:
                if not has_reference:
                    raise
                existing = await session.scalar(select(PointTransaction).where(
                    PointTransaction.user_id == user_id,
                    PointTransaction.chat_id == chat_id,
                    PointTransaction.reference_type == reference_type,
                    PointTransaction.reference_id == reference_id,
                ))
                if existing is None:
                    raise
            if commit:
                await session.commit()
            await session.refresh(profile)
        return profile.points

    async def spend_points(
        self, session: AsyncSession, *, user_id: int, chat_id: int, amount: int,
        reason: str, reference_type: str | None = None, reference_id: str | None = None,
        commit: bool = True,
    ) -> int | None:
        """Atomically spend points and make reference-keyed charges idempotent."""
        if amount <= 0:
            raise ValueError("Point cost must be positive")
        profile = await self.get_or_create_game_profile(session, user_id, chat_id, commit=False)
        has_reference = reference_type is not None and reference_id is not None
        try:
            async with session.begin_nested():
                result = await session.execute(
                    update(GameProfile)
                    .where(GameProfile.id == profile.id, GameProfile.points >= amount)
                    .values(points=GameProfile.points - amount, updated_at=datetime.utcnow())
                )
                if result.rowcount != 1:
                    raise _InsufficientPoints
                session.add(PointTransaction(
                    user_id=user_id, chat_id=chat_id, amount=-amount, reason=reason,
                    reference_type=reference_type, reference_id=reference_id,
                ))
                await session.flush()
        except _InsufficientPoints:
            if commit:
                await session.rollback()
            return None
        except IntegrityError:
            if not has_reference:
                raise
            existing = await session.scalar(select(PointTransaction).where(
                PointTransaction.user_id == user_id,
                PointTransaction.chat_id == chat_id,
                PointTransaction.reference_type == reference_type,
                PointTransaction.reference_id == reference_id,
            ))
            if existing is None:
                raise
        if commit:
            await session.commit()
        await session.refresh(profile)
        return profile.points

    @staticmethod
    async def _ensure_user(session: AsyncSession, user: TgUser, now: datetime) -> None:
        if await session.get(User, user.id) is None:
            session.add(User(
                id=user.id, username=user.username, first_name=user.first_name,
                last_name=user.last_name, language_code=user.language_code,
                is_bot=user.is_bot, created_at=now, last_seen_at=now,
            ))

    @staticmethod
    async def _ensure_chat(session: AsyncSession, chat: TgChat, now: datetime) -> None:
        if await session.get(Chat, chat.id) is None:
            session.add(Chat(
                id=chat.id, type=chat.type, title=chat.title, username=chat.username,
                created_at=now, last_seen_at=now,
            ))


class _InsufficientPoints(Exception):
    pass
