from types import SimpleNamespace

import pytest
from aiogram.exceptions import TelegramBadRequest

from app.core.processing_feedback import (
    ProcessingFeedback,
    ProcessingResultDTO,
    WAITING_MESSAGES,
)


class FakeTransient:
    def __init__(self, *, reject_edit: bool = False) -> None:
        self.edits: list[tuple[str, dict]] = []
        self.deleted = False
        self.reject_edit = reject_edit

    async def edit_text(self, text: str, **kwargs):
        if self.reject_edit:
            raise TelegramBadRequest(method=None, message="edit rejected")
        self.edits.append((text, kwargs))
        return self

    async def delete(self):
        self.deleted = True


class FakeTarget:
    def __init__(self, transient: FakeTransient) -> None:
        self.answers: list[tuple[str, dict]] = []
        self.transient = transient

    async def answer(self, text: str, **kwargs):
        self.answers.append((text, kwargs))
        return self.transient


@pytest.mark.asyncio
async def test_processing_feedback_uses_only_authored_waiting_messages():
    target = FakeTarget(FakeTransient())
    feedback = ProcessingFeedback(target, chooser=lambda choices: choices[1])

    await feedback.start()

    assert target.answers == [(WAITING_MESSAGES[1], {})]


@pytest.mark.asyncio
async def test_processing_feedback_replaces_transient_with_final_result():
    target = FakeTarget(FakeTransient())
    feedback = ProcessingFeedback(target, chooser=lambda choices: choices[0])
    markup = SimpleNamespace()

    await feedback.start()
    sent = await feedback.finish(ProcessingResultDTO("🎉 Resultado", reply_markup=markup))
    await feedback.cleanup()

    assert sent is target.transient
    assert target.transient.edits == [
        ("🎉 Resultado", {"reply_markup": markup})
    ]
    assert target.transient.deleted is False


@pytest.mark.asyncio
async def test_processing_feedback_falls_back_when_edit_is_rejected():
    target = FakeTarget(FakeTransient(reject_edit=True))
    feedback = ProcessingFeedback(target)

    await feedback.start()
    sent = await feedback.finish("Resultado final")

    assert sent is target.transient
    assert target.transient.deleted is True
    assert target.answers[-1] == ("Resultado final", {"reply_markup": None})


@pytest.mark.asyncio
async def test_processing_feedback_cleans_up_when_no_result_arrives():
    target = FakeTarget(FakeTransient())
    feedback = ProcessingFeedback(target)

    await feedback.start()
    await feedback.cleanup()

    assert target.transient.deleted is True
