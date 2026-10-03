# -*- coding: utf-8 -*-
from types import SimpleNamespace

import run_all


def test_invalid_preflight_prevents_all_child_process_creation(monkeypatch, capsys):
    process_calls = []

    def failing_import(module_name):
        raise ModuleNotFoundError(
            "No module named 'api'",
            name="api",
        )

    def forbidden_process(*args, **kwargs):
        process_calls.append((args, kwargs))
        raise AssertionError(
            "multiprocessing.Process must not be called after preflight failure"
        )

    monkeypatch.setattr(run_all.importlib, "import_module", failing_import)
    monkeypatch.setattr(run_all.multiprocessing, "Process", forbidden_process)

    exit_code = run_all.main()

    captured = capsys.readouterr()
    assert exit_code == 1
    assert process_calls == []
    assert "[STARTUP PREFLIGHT] FAIL" in captured.err
    assert "FastAPI" in captured.err
    assert "api" in captured.err


def test_valid_preflight_completes_without_starting_runtime_services(monkeypatch):
    modules = {
        "src.api.main": SimpleNamespace(
            app=lambda *args, **kwargs: None,
        ),
        "src.bot.main": SimpleNamespace(
            create_bot_app=lambda: None,
        ),
        "src.discord.bot": SimpleNamespace(
            run_discord_bot=lambda: None,
        ),
    }

    def fake_import(module_name):
        return modules[module_name]

    monkeypatch.setattr(run_all.importlib, "import_module", fake_import)

    assert run_all.preflight_startup() is None
