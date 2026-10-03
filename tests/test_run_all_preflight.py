# -*- coding: utf-8 -*-
import importlib
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace


def test_invalid_preflight_prevents_all_child_process_creation(monkeypatch, capsys):
    run_all = importlib.import_module("run_all")
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
    run_all = importlib.import_module("run_all")
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


def test_run_all_import_surface_does_not_require_uvicorn(tmp_path):
    root = Path(__file__).resolve().parents[1]
    script = tmp_path / "import_run_all_without_uvicorn.py"
    script.write_text(
        """
import importlib.abc
import sys

class BlockUvicorn(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "uvicorn" or fullname.startswith("uvicorn."):
            raise ModuleNotFoundError("uvicorn intentionally blocked")
        return None

sys.meta_path.insert(0, BlockUvicorn())
import run_all

assert hasattr(run_all, "preflight_startup")
""",
        encoding="utf-8",
    )

    env = dict(__import__("os").environ)
    env["PYTHONPATH"] = str(root)

    completed = subprocess.run(
        [sys.executable, str(script)],
        cwd=root,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
