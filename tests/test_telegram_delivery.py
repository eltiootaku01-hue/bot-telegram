import pytest
from aiogram.exceptions import TelegramRetryAfter
from aiogram.methods import SendMessage

from app.services.telegram_delivery import with_retry_after


@pytest.mark.asyncio
async def test_with_retry_after_waits_using_server_retry_value() -> None:
    method = SendMessage(chat_id=-100, text="test")
    error = TelegramRetryAfter(method, "slow", 7)
    calls = 0
    waits: list[float] = []

    async def operation() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise error
        return "ok"

    async def fake_sleep(seconds: float) -> None:
        waits.append(seconds)

    result = await with_retry_after(operation, sleep=fake_sleep)

    assert result == "ok"
    assert calls == 2
    assert waits == [7.0]


@pytest.mark.asyncio
async def test_with_retry_after_stops_after_configured_retries() -> None:
    method = SendMessage(chat_id=-100, text="test")
    error = TelegramRetryAfter(method, "slow", 3)
    calls = 0

    async def operation() -> None:
        nonlocal calls
        calls += 1
        raise error

    async def fake_sleep(seconds: float) -> None:
        return None

    with pytest.raises(TelegramRetryAfter):
        await with_retry_after(operation, max_retries=2, sleep=fake_sleep)

    assert calls == 3


@pytest.mark.asyncio
async def test_with_retry_after_does_not_retry_other_failures() -> None:
    calls = 0

    async def operation() -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError("network failure")

    async def fake_sleep(seconds: float) -> None:
        raise AssertionError("sleep must not be called")

    with pytest.raises(RuntimeError, match="network failure"):
        await with_retry_after(operation, sleep=fake_sleep)

    assert calls == 1
