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


def test_local_social_composer_roll_is_deterministic() -> None:
    composer = LocalSocialComposer()

    assert composer.compose(BotIdentity.CARI, roll=0) == composer.compose(BotIdentity.CARI, roll=2)
    assert composer.compose(BotIdentity.CARI, roll=0) != composer.compose(BotIdentity.CARI, roll=1)


def test_social_runtime_module_uses_normal_module_contract() -> None:
    module = SocialRuntimeModule.__new__(SocialRuntimeModule)

    assert module.name == "social_runtime"
