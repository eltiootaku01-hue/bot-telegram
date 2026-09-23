import json
from pathlib import Path
from random import Random

import pytest

from app.dialogues.models import DialogueEvent
from app.dialogues.renderer import DialogueRenderer
from app.dialogues.store import DialogueStore


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIALOGUES = ROOT / "config" / "dialogues.json"


def test_default_dialogue_catalog_is_valid() -> None:
    catalog = DialogueStore(DEFAULT_DIALOGUES).load()

    assert DialogueEvent.ON_CAMPANA_RUNG in catalog.entries
    assert catalog.phrases(DialogueEvent.ON_CARD_ROLL, "sunna")
    assert catalog.phrases(DialogueEvent.ON_WAIFU_POKER, "cari")


def test_renderer_replaces_placeholders_offline(tmp_path: Path) -> None:
    path = tmp_path / "dialogues.json"
    path.write_text(
        json.dumps({
            "ON_CARD_ROLL": {"sunna": ["Carta: {card_name}"]},
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    renderer = DialogueRenderer(DialogueStore(path), rng=Random(0))

    assert renderer.render(
        DialogueEvent.ON_CARD_ROLL,
        "sunna",
        {"card_name": "#001 Rei Ayanami R"},
    ) == "Carta: #001 Rei Ayanami R"


def test_renderer_rejects_missing_variables(tmp_path: Path) -> None:
    path = tmp_path / "dialogues.json"
    path.write_text(
        json.dumps({
            "ON_CARD_ROLL": {"sunna": ["Carta: {card_name}"]},
        }),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Missing dialogue variables"):
        DialogueRenderer(DialogueStore(path), rng=Random(0)).render(
            DialogueEvent.ON_CARD_ROLL,
            "sunna",
        )


def test_store_upsert_replace_remove_are_atomic_and_reversible(tmp_path: Path) -> None:
    path = tmp_path / "dialogues.json"
    path.write_text(
        json.dumps({"ON_WELCOME": {"cari": ["Hola {user_name}"]}}),
        encoding="utf-8",
    )
    store = DialogueStore(path)

    store.upsert(DialogueEvent.ON_WELCOME, "cari", "Bienvenido {user_name}")
    store.replace(DialogueEvent.ON_WELCOME, "cari", 0, "Hola de nuevo {user_name}")
    store.remove(DialogueEvent.ON_WELCOME, "cari", 1)

    assert store.load().phrases(DialogueEvent.ON_WELCOME, "cari") == (
        "Hola de nuevo {user_name}",
    )
