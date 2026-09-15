from dataclasses import dataclass

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identity import BotIdentity
from app.core.time import utc_now
from app.db.world_models import WorldCatalogEntry, WorldUsageStat


@dataclass(frozen=True, slots=True)
class WorldInsight:
    hot: list[tuple[str, int]]
    cold: list[tuple[str, int]]
    unseen: list[tuple[str, str]]


class WorldService:
    """Small, deterministic observation layer for Ciudad Animals.

    It stores aggregates instead of raw chat text. A future AI curator can read
    these aggregates and suggest world changes without becoming the runtime brain.
    """

    async def observe(
        self,
        session: AsyncSession,
        *,
        bot_identity: BotIdentity | str,
        entry_type: str,
        entry_key: str,
        scope_type: str = "world",
        scope_id: str = "global",
        delta: int = 1,
    ) -> WorldUsageStat:
        if not entry_type.strip() or not entry_key.strip():
            raise ValueError("World observations require entry_type and entry_key")
        if delta <= 0:
            raise ValueError("World observation delta must be positive")

        identity = str(bot_identity)
        stat = await session.scalar(
            select(WorldUsageStat).where(
                WorldUsageStat.bot_identity == identity,
                WorldUsageStat.scope_type == scope_type,
                WorldUsageStat.scope_id == scope_id,
                WorldUsageStat.entry_type == entry_type,
                WorldUsageStat.entry_key == entry_key,
            )
        )
        now = utc_now()
        if stat is None:
            stat = WorldUsageStat(
                bot_identity=identity,
                scope_type=scope_type,
                scope_id=scope_id,
                entry_type=entry_type,
                entry_key=entry_key,
                count=delta,
                first_seen_at=now,
                last_seen_at=now,
            )
            session.add(stat)
        else:
            stat.count += delta
            stat.last_seen_at = now
        await session.flush()
        return stat

    async def register_catalog_entry(
        self,
        session: AsyncSession,
        *,
        bot_identity: BotIdentity | str,
        entry_type: str,
        entry_key: str,
        label: str,
        priority: int = 0,
        enabled: bool = True,
    ) -> WorldCatalogEntry:
        identity = str(bot_identity)
        entry = await session.scalar(
            select(WorldCatalogEntry).where(
                WorldCatalogEntry.bot_identity == identity,
                WorldCatalogEntry.entry_type == entry_type,
                WorldCatalogEntry.entry_key == entry_key,
            )
        )
        if entry is None:
            entry = WorldCatalogEntry(
                bot_identity=identity,
                entry_type=entry_type,
                entry_key=entry_key,
                label=label,
                priority=priority,
                enabled=enabled,
            )
            session.add(entry)
        else:
            entry.label = label
            entry.priority = priority
            entry.enabled = enabled
            entry.updated_at = utc_now()
        await session.flush()
        return entry

    async def user_summary(
        self,
        session: AsyncSession,
        *,
        bot_identity: BotIdentity | str,
        user_id: int,
        chat_id: int | None = None,
        limit: int = 20,
    ) -> list[WorldUsageStat]:
        scope_id = str(user_id) if chat_id is None else f"{user_id}:{chat_id}"
        result = await session.scalars(
            select(WorldUsageStat)
            .where(
                WorldUsageStat.bot_identity == str(bot_identity),
                WorldUsageStat.scope_type == ("user" if chat_id is None else "user_chat"),
                WorldUsageStat.scope_id == scope_id,
            )
            .order_by(desc(WorldUsageStat.count), desc(WorldUsageStat.last_seen_at))
            .limit(limit)
        )
        return list(result)

    async def insights(
        self,
        session: AsyncSession,
        *,
        bot_identity: BotIdentity | str,
        limit: int = 10,
    ) -> WorldInsight:
        identity = str(bot_identity)
        hot_rows = await session.execute(
            select(WorldUsageStat.entry_key, func.sum(WorldUsageStat.count).label("uses"))
            .where(
                WorldUsageStat.bot_identity == identity,
                WorldUsageStat.scope_type == "world",
            )
            .group_by(WorldUsageStat.entry_key)
            .order_by(desc("uses"), WorldUsageStat.entry_key.asc())
            .limit(limit)
        )
        hot = [(key, int(uses)) for key, uses in hot_rows.all()]

        cold_rows = await session.execute(
            select(WorldUsageStat.entry_key, func.sum(WorldUsageStat.count).label("uses"))
            .where(
                WorldUsageStat.bot_identity == identity,
                WorldUsageStat.scope_type == "world",
            )
            .group_by(WorldUsageStat.entry_key)
            .order_by(func.sum(WorldUsageStat.count).asc(), WorldUsageStat.entry_key.asc())
            .limit(limit)
        )
        cold = [(key, int(uses)) for key, uses in cold_rows.all()]

        used_keys = select(WorldUsageStat.entry_key).where(
            WorldUsageStat.bot_identity == identity,
            WorldUsageStat.scope_type == "world",
        )
        unseen_rows = await session.execute(
            select(WorldCatalogEntry.entry_key, WorldCatalogEntry.label)
            .where(
                WorldCatalogEntry.bot_identity == identity,
                WorldCatalogEntry.enabled.is_(True),
                ~WorldCatalogEntry.entry_key.in_(used_keys),
            )
            .order_by(desc(WorldCatalogEntry.priority), WorldCatalogEntry.entry_key.asc())
            .limit(limit)
        )
        unseen = [(key, label) for key, label in unseen_rows.all()]
        return WorldInsight(hot=hot, cold=cold, unseen=unseen)
