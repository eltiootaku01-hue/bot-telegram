from app.core.identity import BotIdentity
from app.services.process_catalog import ProcessCatalog, ProcessDefinition, built_in_catalog


def test_builtin_process_catalog_covers_all_bot_workflows() -> None:
    catalog = built_in_catalog()
    for identity in BotIdentity:
        processes = catalog.for_identity(identity)
        assert processes
        assert all(process.owner is identity for process in processes)

    assert catalog.get("cami.media.publish") is not None
    assert catalog.get("chie.request.intake") is not None
    assert catalog.get("sunna.waifumon.capture") is not None


def test_process_search_is_small_and_deterministic() -> None:
    catalog = built_in_catalog()

    first = catalog.search("publicar imagen programar", owner=BotIdentity.CAMI, limit=3)
    second = catalog.search("publicar imagen programar", owner=BotIdentity.CAMI, limit=3)

    assert first == second
    assert len(first) <= 3
    assert first
    assert first[0].process.id in {
        "cami.media.publish",
        "cami.media.schedule",
    }


def test_process_catalog_rejects_invalid_definitions() -> None:
    catalog = ProcessCatalog()
    try:
        catalog.register(ProcessDefinition(
            id="",
            owner=BotIdentity.CARI,
            name="bad",
            category="test",
            objective="bad",
        ))
    except ValueError:
        pass
    else:
        raise AssertionError("empty process ids must be rejected")

    catalog.register(
        ProcessDefinition(
            id="demo",
            owner=BotIdentity.CARI,
            name="Demo",
            category="test",
            objective="demo",
        )
    )
    try:
        catalog.register(
            ProcessDefinition(
                id="demo",
                owner=BotIdentity.CARI,
                name="Duplicate",
                category="test",
                objective="duplicate",
            )
        )
    except ValueError:
        pass
    else:
        raise AssertionError("duplicate process ids must be rejected")


def test_specialty_processes_keep_their_declared_owner() -> None:
    catalog = built_in_catalog()

    expected = {
        "cari.trivia.round": BotIdentity.CARI,
        "cari.trivia.answer": BotIdentity.CARI,
        "cami.mystery.round": BotIdentity.CAMI,
        "cami.mystery.answer": BotIdentity.CAMI,
        "chie.human.verify": BotIdentity.CHIE,
        "chie.community.welcome": BotIdentity.CHIE,
        "chie.community.goodbye": BotIdentity.CHIE,
    }

    for process_id, owner in expected.items():
        process = catalog.get(process_id)
        assert process is not None
        assert process.owner is owner
