from unittest.mock import AsyncMock

import pytest

from app.middleware.member_sync import MemberSyncMiddleware


@pytest.mark.asyncio
async def test_bootstrap_command_does_not_create_member_activity() -> None:
    repository = AsyncMock()
    wake_store = AsyncMock()
    middleware = MemberSyncMiddleware(
        database=None,
        repository=repository,
        wake_store=wake_store,
    )

    async def handler(event, data):
        return "handled"

    result = await middleware(
        handler,
        event=object(),
        data={"chat_access_bootstrap": True},
    )

    assert result == "handled"
    repository.touch.assert_not_awaited()
    wake_store.request_wake.assert_not_awaited()
