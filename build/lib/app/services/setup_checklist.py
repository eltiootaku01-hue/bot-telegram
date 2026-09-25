from __future__ import annotations


def build_setup_checklist(
    *,
    bots: dict[str, dict[str, str]],
    master_id: str,
    base_group_id: str,
    authorized_chat_ids: str,
) -> tuple[str, ...]:
    """Build a human-readable local setup checklist without making network calls."""
    checks: list[str] = []

    master = master_id.strip()
    if master.isdigit() and int(master) > 0:
        checks.append("✓ Maestro/Jefe: ID configurado")
    else:
        checks.append("✗ Maestro/Jefe: falta un ID numérico de Telegram")

    authorized = {
        value.strip()
        for value in authorized_chat_ids.split(",")
        if value.strip()
    }

    for key in ("chie", "cari", "sunna", "cami"):
        fields = bots.get(key, {})
        token_ok = bool(fields.get("token", "").strip())
        link_ok = bool(fields.get("link", "").strip())
        if token_ok and link_ok:
            checks.append(f"✓ {key.title()}: token y enlace cargados")
        elif token_ok:
            checks.append(f"⚠ {key.title()}: token cargado, falta enlace (se puede obtener al verificar)")
        elif link_ok:
            checks.append(f"⚠ {key.title()}: enlace cargado, falta token")
        else:
            checks.append(f"✗ {key.title()}: faltan token y enlace")

    if base_group_id.strip() == "0" or not base_group_id.strip():
        checks.append("⚠ Grupo base: todavía no definido")
    else:
        try:
            base = int(base_group_id.strip())
        except ValueError:
            base = 0
        if base >= 0:
            checks.append("✗ Grupo base: debe ser un ID negativo")
        elif str(base) in authorized:
            checks.append("✓ Grupo base: definido y autorizado")
        else:
            checks.append("⚠ Grupo base: definido pero todavía no autorizado")

    if authorized:
        checks.append(f"✓ Allowlist: {len(authorized)} chat(s) autorizado(s)")
    else:
        checks.append("⚠ Allowlist: ningún grupo/supergrupo autorizado")

    checks.append("⚠ Telegram remoto: presencia/permisos se comprueban desde «Asistente Telegram»")
    return tuple(checks)
