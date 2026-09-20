from app.characters.director import CharacterDirector
from app.characters.models import CharacterIntent
from app.core.identity import BotIdentity


def test_every_directed_character_pair_has_an_authored_interaction() -> None:
    director = CharacterDirector()
    identities = tuple(BotIdentity)

    for speaker in identities:
        for partner in identities:
            if speaker is partner:
                continue
            responses = [
                director.choose_interaction(
                    speaker,
                    partner,
                    intent,
                    roll=0,
                )
                for intent in CharacterIntent
            ]
            response = next((item for item in responses if item is not None), None)
            assert response is not None, (
                f"Missing authored interaction: {speaker.value} -> {partner.value}"
            )
            assert response.scene.speaker is speaker
            assert response.follow_up is not None
            assert response.follow_up.speaker is partner
