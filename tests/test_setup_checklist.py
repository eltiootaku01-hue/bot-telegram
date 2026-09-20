from app.services.setup_checklist import build_setup_checklist


def test_setup_checklist_marks_missing_and_ready_items() -> None:
    checks = build_setup_checklist(
        bots={
            "chie": {"token": "token", "link": "https://t.me/ChieBot"},
            "cari": {"token": "", "link": "https://t.me/CariBot"},
            "sunna": {"token": "token", "link": ""},
            "cami": {"token": "", "link": ""},
        },
        master_id="123456",
        base_group_id="-100123",
        authorized_chat_ids="-100123",
    )

    assert "✓ Maestro/Jefe: ID configurado" in checks
    assert "✓ Chie: token y enlace cargados" in checks
    assert "⚠ Cari: enlace cargado, falta token" in checks
    assert "⚠ Sunna: token cargado, falta enlace (se puede obtener al verificar)" in checks
    assert "✗ Cami: faltan token y enlace" in checks
    assert "✓ Grupo base: definido y autorizado" in checks
    assert any("Telegram remoto" in item for item in checks)


def test_setup_checklist_flags_unsafe_base_group_state() -> None:
    checks = build_setup_checklist(
        bots={
            name: {"token": "token", "link": f"https://t.me/{name}Bot"}
            for name in ("chie", "cari", "sunna", "cami")
        },
        master_id="0",
        base_group_id="-100999",
        authorized_chat_ids="",
    )

    assert "✗ Maestro/Jefe: falta un ID numérico de Telegram" in checks
    assert "⚠ Grupo base: definido pero todavía no autorizado" in checks
    assert "⚠ Allowlist: ningún grupo/supergrupo autorizado" in checks
