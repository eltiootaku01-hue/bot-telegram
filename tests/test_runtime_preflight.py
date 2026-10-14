# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import pytest

from bot_ia import preflight
from bot_ia.config.dotenv import load_dotenv


_UNIVERSES = {
    "one_neko_punch": ("One Neko Punch", "BOT_IA_ONE_NEKO_PUNCH_ROOT"),
    "neko_fish_online": ("Neko Fish Online", "BOT_IA_NEKO_FISH_ONLINE_ROOT"),
    "neko_of_the_dead": ("Neko of the Dead", "BOT_IA_NEKO_OF_THE_DEAD_ROOT"),
    "my_neko_academia": ("My Neko Academia", "BOT_IA_MY_NEKO_ACADEMIA_ROOT"),
    "attack_on_neko": ("Attack on Neko", "BOT_IA_ATTACK_ON_NEKO_ROOT"),
}


def _project(tmp_path: Path, *, account_key: str = "OPENAI_API_KEY") -> Path:
    root = tmp_path / "project"
    config_dir = root / "config"
    config_dir.mkdir(parents=True)
    lines = [
        "[providers.openai]",
        'enabled = true',
        'model = "test-model"',
        'fallback = ""',
        "",
        "[providers.openai.accounts.main]",
        f'secret_env = "{account_key}"',
        'enabled = true',
        "",
        "[services.telegram]",
        "enabled = false",
        "",
    ]
    for universe_id, (name, env_name) in _UNIVERSES.items():
        universe_root = root / "libraries" / universe_id
        universe_root.mkdir(parents=True)
        (universe_root / "chapter.md").write_text("test inventory entry", encoding="utf-8")
        lines.extend([
            f"[universes.{universe_id}]",
            f'display_name = "{name}"',
            f'root_path = "env:{env_name}"',
            'language = "es"',
            "",
        ])
        os.environ[env_name] = str(universe_root)
    (config_dir / "runtime.toml").write_text("\n".join(lines), encoding="utf-8")
    return root


@pytest.fixture(autouse=True)
def _clean_test_environment(monkeypatch):
    for name in (
        "OPENAI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "COZE_API_TOKEN",
        "TELEGRAM_BOT_TOKEN", "BOT_IA_PROVIDER",
        *(env_name for _, env_name in _UNIVERSES.values()),
    ):
        monkeypatch.delenv(name, raising=False)


def test_valid_configuration_has_stable_json_and_exit_code(tmp_path, monkeypatch, capsys):
    root = _project(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-secret")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "telegram-test-token")
    first, code = preflight.build_report(root)
    second, second_code = preflight.build_report(root)
    assert code == second_code == 0
    assert first == second
    assert first["configuration"]["status"] == "VALID"
    assert first["overall_status"] == "READY"
    assert len(first["universes"]) == 5
    assert all(item["inventory_entries"] == 1 for item in first["universes"])
    assert preflight.run_preflight(root) == 0
    output = capsys.readouterr().out
    assert json.loads(output)["overall_status"] == "READY"
    assert "unit-test-secret" not in output
    assert "telegram-test-token" not in output


def test_missing_or_invalid_runtime_config_returns_invalid_code(tmp_path):
    report, code = preflight.build_report(tmp_path)
    assert code == preflight._EXIT_INVALID
    assert report["configuration"]["status"] == "INVALID"
    assert report["overall_status"] == "BLOCKED"
    root = _project(tmp_path / "invalid")
    (root / "config" / "runtime.toml").write_text("not = [valid", encoding="utf-8")
    report, code = preflight.build_report(root)
    assert code == preflight._EXIT_INVALID
    assert report["configuration"]["status"] == "INVALID"
    assert report["configuration"]["error_type"] == "TOMLDecodeError"


def test_missing_provider_variables_blocks_without_leaking_values(tmp_path, capsys):
    root = _project(tmp_path)
    report, code = preflight.build_report(root)
    assert code == preflight._EXIT_BLOCKED
    assert report["overall_status"] == "BLOCKED"
    assert report["providers"][0]["accounts"][0]["credential_present"] is False
    assert preflight.run_preflight(root) == preflight._EXIT_BLOCKED
    output = capsys.readouterr().out
    assert "OPENAI_API_KEY" in output
    assert "credential_present" in output


def test_telegram_token_presence_never_prints_value(tmp_path, monkeypatch, capsys):
    root = _project(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "provider-secret-value")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-telegram-secret")
    report, code = preflight.build_report(root)
    assert code == 0
    assert report["telegram"]["token_present"] is True
    assert report["telegram"]["authentication"] == "NOT_CHECKED"
    preflight.run_preflight(root)
    output = capsys.readouterr().out
    assert "fake-telegram-secret" not in output
    assert "provider-secret-value" not in output


def test_five_universe_roots_are_reported_with_deterministic_counts(tmp_path, monkeypatch):
    root = _project(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "present")
    report, _ = preflight.build_report(root)
    assert [item["id"] for item in report["universes"]] == list(_UNIVERSES)
    assert all(item["root_configured"] for item in report["universes"])
    assert all(item["directory_accessible"] for item in report["universes"])
    assert all(item["inventory_status"] == "OK" for item in report["universes"])
    assert all(item["inventory_entries"] == 1 for item in report["universes"])


def test_dotenv_respects_existing_process_environment(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("PREFLIGHT_EXISTING=from-file\nPREFLIGHT_NEW=from-file\n", encoding="utf-8")
    monkeypatch.setenv("PREFLIGHT_EXISTING", "from-process")
    monkeypatch.delenv("PREFLIGHT_NEW", raising=False)
    load_dotenv(env_file)
    assert os.environ["PREFLIGHT_EXISTING"] == "from-process"
    assert os.environ["PREFLIGHT_NEW"] == "from-file"


def test_cli_dispatches_preflight_before_building_runtime(tmp_path, monkeypatch, capsys):
    from bot_ia import __main__ as entrypoint

    root = _project(tmp_path)
    monkeypatch.setattr(entrypoint, "PROJECT_ROOT", root)
    monkeypatch.setenv("OPENAI_API_KEY", "present")
    monkeypatch.setattr(sys, "argv", ["bot_ia", "--mode", "preflight"])
    monkeypatch.setattr(entrypoint, "_build_application", lambda _root: pytest.fail("runtime builder must not be called"))
    with pytest.raises(SystemExit) as raised:
        entrypoint.main()
    assert raised.value.code == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "preflight"


def test_preflight_does_not_construct_runtime_or_touch_database(tmp_path, monkeypatch):
    root = _project(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "present")
    called = {"runtime": False}
    def forbidden(*_args, **_kwargs):
        called["runtime"] = True
        raise AssertionError("runtime must not be constructed")
    monkeypatch.setattr("bot_ia.runtime.build_runtime", forbidden)
    report, code = preflight.build_report(root)
    assert code == 0
    assert report["overall_status"] == "WARNING"  # Telegram token is absent.
    assert called["runtime"] is False
    assert not list(root.rglob("*.sqlite*"))


def test_errors_are_sanitized_and_inventory_limits_are_reported(tmp_path, monkeypatch, capsys):
    root = _project(tmp_path)
    (root / "config" / "runtime.toml").write_text("not = [valid", encoding="utf-8")
    monkeypatch.setenv("SENSITIVE_SENTINEL", "never-print-this-secret")
    report, code = preflight.build_report(root)
    assert code == preflight._EXIT_INVALID
    assert "never-print-this-secret" not in json.dumps(report)
    preflight.run_preflight(root)
    assert "never-print-this-secret" not in capsys.readouterr().out
    large_root = root / "oversized"
    large_root.mkdir()
    (large_root / "large.md").write_bytes(b"x" * (preflight._MAX_SOURCE_BYTES + 1))
    bounded, reason = preflight._inventory_is_bounded(large_root)
    assert bounded is False
    assert reason == "LIMIT_EXCEEDED"
