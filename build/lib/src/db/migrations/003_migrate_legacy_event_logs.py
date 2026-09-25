from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from src.db.event_repository import EventRepository


async def migrate_legacy_events(db_path: str) -> dict[str, int]:
    """Migrate event_logs into platform-neutral events plus Telegram deliveries."""
    repo = EventRepository(db_path)
    await repo.init_db()

    import aiosqlite

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM event_logs ORDER BY created_at ASC"
        ) as cursor:
            legacy_events = [dict(row) for row in await cursor.fetchall()]

    migrated = 0
    deliveries = 0

    for event in legacy_events:
        created = await repo.create_notification_event(
            event_id=event["event_id"],
            event_type=event["event_type"],
            title=event["title"],
            url=event["url"],
            author=event["author"],
        )
        if created:
            migrated += 1

        delivery_id = f"telegram:{event['event_id']}"
        created_delivery = await repo.create_delivery(
            delivery_id=delivery_id,
            event_id=event["event_id"],
            platform="telegram",
            destination_id=event["thread_id"],
            max_retries=event["max_retries"],
        )

        # Preserve the terminal/non-terminal state of the legacy delivery.
        import aiosqlite as _aiosqlite

        async with _aiosqlite.connect(db_path) as db:
            if event["status"] == "DELIVERED":
                await db.execute(
                    """
                    UPDATE notification_deliveries
                    SET status='DELIVERED',
                        retry_count=?,
                        external_message_id=?,
                        last_error=NULL,
                        created_at=?,
                        updated_at=?
                    WHERE delivery_id=?
                    """,
                    (
                        event["retry_count"],
                        str(event["telegram_message_id"])
                        if event["telegram_message_id"] is not None
                        else None,
                        event["created_at"],
                        event["updated_at"],
                        delivery_id,
                    ),
                )
            elif event["status"] == "FAILED":
                await db.execute(
                    """
                    UPDATE notification_deliveries
                    SET status='FAILED', retry_count=?, last_error=?,
                        created_at=?, updated_at=?
                    WHERE delivery_id=?
                    """,
                    (
                        event["retry_count"],
                        event["last_error"],
                        event["created_at"],
                        event["updated_at"],
                        delivery_id,
                    ),
                )
            else:
                await db.execute(
                    """
                    UPDATE notification_deliveries
                    SET status=?, retry_count=?, last_error=?,
                        created_at=?, updated_at=?
                    WHERE delivery_id=?
                    """,
                    (
                        event["status"],
                        event["retry_count"],
                        event["last_error"],
                        event["created_at"],
                        event["updated_at"],
                        delivery_id,
                    ),
                )
            await db.commit()

        if created_delivery:
            deliveries += 1

    return {"legacy_events": len(legacy_events), "events_migrated": migrated, "deliveries_created": deliveries}


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate legacy event_logs to relational notifications")
    parser.add_argument("db_path", nargs="?", default="data/command_center_events.db")
    args = parser.parse_args()
    result = asyncio.run(migrate_legacy_events(args.db_path))
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
