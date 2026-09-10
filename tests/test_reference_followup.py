from datetime import datetime, timedelta, timezone

from bot_ia.contracts import SessionState
from bot_ia.core.models import EntityCandidate
from bot_ia.core.references import ReferenceResolver


def test_pronoun_uses_recent_entity_from_session():
    state = SessionState(
        "session-1",
        "one_neko_punch",
        datetime.now(timezone.utc) + timedelta(hours=1),
        recent_reference_ids=("kuro",),
    )
    candidates = (EntityCandidate("kuro", "one_neko_punch", "Kuro"),)
    result = ReferenceResolver().resolve("¿y ella qué hace?", "one_neko_punch", candidates, state)
    assert len(result) == 1
    assert result[0].resolved_entity_id == "kuro"
    assert not result[0].clarification_needed
