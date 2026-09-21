from types import SimpleNamespace

import pytest

from app.core.processing_feedback import ProcessingFeedback, ProcessingResultDTO, WAITING_MESSAGES


class FakeTransient:
    def __init__(self) -> None:
        self.edits = []
        self.deleted = False

    async def edit_text(self, text: str, **kwargs):
        self.edits.append((text, kwargs))

    async def delete(self):
        self.deleted = True


class FakeTarget:
    def __init__(self) -> None:
        self.answers = []

    async def answer(self, text: str, **kwargs):
        self.answers.append((text, kwargs))
        return FakeTransient()


@pytest.mark.asyncio
async def test_processing_feedback_uses_only_authored_waiting_messages():
    target = FakeTarget()
    feedback = ProcessingFeedback(target, chooser=lambda choices: choices[1])

    await feedback.start()

    assert target.answers == [(WAITING_MESSAGES[1], {})]


@pytest.mark.asyncio
async def test_processing_feedback_replaces_transient_with_final_result():
    target = FakeTarget()
    transient = FakeTransient()
    target.answer = lambda text, **kwargs: _answer(transient, target, text, kwargs)
    feedback = ProcessingFeedback(target, chooser=lambda choices: choices[0])

    await feedback.start()
    await feedback.finish(
        ProcessingResultDTO("🎉 Resultado", reply_markup=SimpleNamespace())
    )
    await feedback.cleanup()

    assert transient.edits == [
        ("🎉 Resultado", {"reply_markup": transient.edits[0][1]["reply_markup"]})
    ]
    assert transient.deleted is False


async def _answer(transient, target, text, kwargs):
    target.answers.append((text, kwargs))
    return transient


@pytest.mark.asyncio
async def test_processing_feedback_cleans_up_when_no_result_arrives():
    target = FakeTarget()
    transient = FakeTransient()
    target.answer = lambda text, **kwargs: _answer(transient, target, text, kwargs)
    feedback = ProcessingFeedback(target)

    await feedback.start()
    await feedback.cleanup()

    assert transient.deleted is True
