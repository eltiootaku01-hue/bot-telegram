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


def test_confirmed_relationships_have_multiple_authored_variants() -> None:
    director = CharacterDirector()

    for speaker, partner, intent in (
        (BotIdentity.CARI, BotIdentity.CAMI, CharacterIntent.AFFECTION),
        (BotIdentity.CAMI, BotIdentity.CARI, CharacterIntent.AFFECTION),
        (BotIdentity.CARI, BotIdentity.SUNNA, CharacterIntent.BELONGING),
        (BotIdentity.SUNNA, BotIdentity.CARI, CharacterIntent.BELONGING),
        (BotIdentity.CAMI, BotIdentity.SUNNA, CharacterIntent.BELONGING),
        (BotIdentity.SUNNA, BotIdentity.CAMI, CharacterIntent.BELONGING),
    ):
        first = director.choose_interaction(speaker, partner, intent, roll=0)
        second = director.choose_interaction(speaker, partner, intent, roll=1)

        assert first is not None
        assert second is not None
        assert first.scene.key != second.scene.key
        assert first.follow_up is not None
        assert second.follow_up is not None
        assert first.follow_up.speaker is partner
        assert second.follow_up.speaker is partner
