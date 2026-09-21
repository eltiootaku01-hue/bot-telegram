from pathlib import Path


WORLD_CORE_FILES = (
    "app/world/models.py",
    "app/world/service.py",
    "app/world/runtime.py",
    "app/world/presenter.py",
    "app/world/tools.py",
)


def test_world_core_does_not_depend_on_telegram_or_character_runtime() -> None:
    for relative_path in WORLD_CORE_FILES:
        source = Path(relative_path).read_text(encoding="utf-8")
        assert "from aiogram" not in source
        assert "import aiogram" not in source
        assert "app.characters" not in source
        assert "app.modules" not in source
