from __future__ import annotations
from app.dialogues.models import DialogueEvent
from app.multibot.dialogues.manager import DialogueManager
from .models import ConversationIntent, ConversationState
from .parser import DeterministicParser
from .state import StateStore

_EVENT = {
 "GREETING": DialogueEvent.ON_WELCOME,
 "GAME_INVITE": DialogueEvent.ON_WAIFU_POKER,
 "CAMPANA": DialogueEvent.ON_CAMPANA_RUNG,
 "CAMPANA_FULL": DialogueEvent.ON_CAMPANA_RUNG,
 "GACHA_ROLL": DialogueEvent.ON_CARD_ROLL,
}

class ConversationEngine:
    def __init__(self, dialogues: DialogueManager, *, state=None, parser=None) -> None:
        self.dialogues, self.state, self.parser = dialogues, state or StateStore(), parser or DeterministicParser()

    def handle(self, *, identity: str, user_id: int, text: str | None, user_name: str = "amigo", cooldown_seconds: int = 0) -> str:
        parsed = self.parser.parse(text)
        try:
            self.state.transition(identity, user_id, parsed.intent, cooldown_seconds=cooldown_seconds)
        except ValueError as exc:
            return self.dialogues.fallback(identity, {"user_name": user_name, "seconds": self.state.remaining(identity, user_id)})
        if parsed.intent is ConversationIntent.STATUS_QUERY:
            return f"Estado: {self.state.snapshot(identity, user_id).state.value}."
        event = _EVENT.get(parsed.intent.value)
        if event is not None:
            variables = {"user_name": user_name, "seconds": self.state.remaining(identity, user_id)}
            return self.dialogues.render(event, identity, variables)
        return self.dialogues.fallback(identity, {"user_name": user_name})
