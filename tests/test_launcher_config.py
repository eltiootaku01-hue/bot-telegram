from __future__ import annotations

from pathlib import Path

import app.launcher as launcher


class DummyRoot:
    def __init__(self, path: Path) -> None:
        self.path = path


def test_env_defaults_include_chat_access_policy() -> None:
    assert launcher.ENV_DEFAULTS["AUTHORIZED_CHAT_IDS"] == ""
    assert launcher.ENV_DEFAULTS["ALLOW_ADMIN_PRIVATE_CHAT"] == "true"


def test_save_config_persists_chat_access_policy(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str]] = []

    class FakeVar:
        def __init__(self, value: str | bool) -> None:
            self.value = value

        def get(self):
            return self.value

        def set(self, value) -> None:
            self.value = value

    class FakeEntry:
        def get(self) -> str:
            return ""

    class FakeLauncher:
        def __init__(self) -> None:
            self.authorized_chats_var = FakeVar("-100111,-100222")
            self.allow_admin_private_var = FakeVar(False)
            self.provider_var = FakeVar("")
            self.model_var = FakeVar("llama3.2:1b")
            self.admin_var = FakeVar("123")
            self.media_var = FakeVar("0")
            self.ai_global_var = FakeVar(False)
            self.ai_bot_vars = {name: FakeVar(False) for name in launcher.BOTS}
            self.ai_vars = {name: FakeVar("") for name, _ in launcher.AI_FIELDS}
            self.bot_vars = {
                name: {"link": FakeVar(f"https://t.me/{name}"), "token": FakeVar("token")}
                for name in launcher.BOTS
            }
            self.status = FakeVar("")

        def save_config(self) -> bool:
            return launcher.BotLauncher.save_config(self)

    def fake_set_key(path: str, key: str, value: str, **_: object) -> None:
        calls.append((key, value))

    monkeypatch.setattr(launcher, "ENV_PATH", tmp_path / ".env")
    monkeypatch.setattr(launcher, "set_key", fake_set_key)

    instance = FakeLauncher()
    assert instance.save_config() is True
    values = dict(calls)
    assert values["AUTHORIZED_CHAT_IDS"] == "-100111,-100222"
    assert values["ALLOW_ADMIN_PRIVATE_CHAT"] == "false"
    assert values["ADMIN_USER_ID"] == "123"
