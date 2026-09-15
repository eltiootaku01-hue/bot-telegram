from app.characters.director import CharacterDirector
from app.characters.models import CharacterIntent
from app.core.identity import BotIdentity
from app.core.social_runtime import LocalSocialComposer, SocialRuntimeModule


def test_local_social_composer_has_distinct_identity_voice() -> None:
    composer = LocalSocialComposer()

    messages = {
        identity: composer.compose(identity, roll=0)
        for identity in BotIdentity
    }

    assert set(messages) == set(BotIdentity)
    assert len(set(messages.values())) == len(BotIdentity)
    assert all(message for message in messages.values())


def test_local_social_composer_uses_authored_director_intents() -> None:
    composer = LocalSocialComposer()
    director = CharacterDirector()

    for identity in BotIdentity:
        intent = composer._LOCAL_INTENTS[identity]
        expected = director.choose(identity, intent, roll=0)
        assert expected is not None
        assert composer.compose(identity, roll=0) == expected.scene.text

    assert composer._LOCAL_INTENTS[BotIdentity.SUNNA] is CharacterIntent.QUIET
    assert composer._LOCAL_INTENTS[BotIdentity.CAMI] is CharacterIntent.BUSY


def test_local_social_composer_roll_is_deterministic() -> None:
    composer = LocalSocialComposer()

    assert composer.compose(BotIdentity.CARI, roll=0) == composer.compose(BotIdentity.CARI, roll=2)
    assert composer.compose(BotIdentity.CARI, roll=0) != composer.compose(BotIdentity.CARI, roll=1)


def test_social_runtime_module_uses_normal_module_contract() -> None:
    module = SocialRuntimeModule.__new__(SocialRuntimeModule)

    assert module.name == "social_runtime"
