from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SetupValidation:
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.errors


def parse_numeric_ids(value: str, *, field_name: str) -> tuple[tuple[int, ...], list[str]]:
    ids: list[int] = []
    errors: list[str] = []
    seen: set[int] = set()
    for raw in value.split(","):
        token = raw.strip()
        if not token:
            continue
        try:
            parsed = int(token)
        except ValueError:
            errors.append(f"{field_name}: '{token}' no es un ID numérico válido.")
            continue
        if parsed in seen:
            errors.append(f"{field_name}: el ID {parsed} está repetido.")
            continue
        seen.add(parsed)
        ids.append(parsed)
    return tuple(ids), errors


def validate_setup(
    *,
    bots: dict[str, dict[str, str]],
    authorized_chat_ids: str,
    admin_user_id: str,
    allow_admin_private_chat: bool,
    allow_user_private_chat: bool,
    media_storage_chat_id: str,
    publish_page_chat_id: str,
    base_group_chat_id: str = "0",
    human_verification_timeout_seconds: str = "120",
    human_verification_raid_window_seconds: str = "60",
    human_verification_raid_threshold: str = "5",
    human_verification_raid_timeout_seconds: str = "45",
) -> SetupValidation:
    errors: list[str] = []
    warnings: list[str] = []

    for key, fields in bots.items():
        if not fields.get("token", "").strip():
            errors.append(f"Falta el token de {key.title()}.")
        elif not fields.get("link", "").strip():
            warnings.append(
                f"El enlace de {key.title()} todavía no está cargado; Verificar token puede obtener su @username."
            )

    authorized, id_errors = parse_numeric_ids(
        authorized_chat_ids,
        field_name="AUTHORIZED_CHAT_IDS",
    )
    errors.extend(id_errors)
    if any(chat_id >= 0 for chat_id in authorized):
        errors.append("AUTHORIZED_CHAT_IDS debe contener IDs negativos de grupos/supergrupos.")

    try:
        admin_id = int(admin_user_id.strip() or "0")
    except ValueError:
        admin_id = 0
        errors.append("MASTER_TELEGRAM_ID / ADMIN_USER_ID debe ser un entero positivo.")
    if (allow_admin_private_chat or not allow_user_private_chat) and admin_id <= 0:
        errors.append("MASTER_TELEGRAM_ID / ADMIN_USER_ID debe ser positivo para configurar el acceso privado del administrador.")

    try:
        base_group_id = int(base_group_chat_id.strip() or "0")
    except ValueError:
        base_group_id = 0
        errors.append("BASE_GROUP_CHAT_ID debe ser 0 o un ID negativo de grupo.")
    if base_group_id > 0:
        errors.append("BASE_GROUP_CHAT_ID debe ser 0 o un ID negativo de grupo.")
    if base_group_id < 0 and base_group_id not in authorized:
        warnings.append("El grupo base todavía no está en AUTHORIZED_CHAT_IDS; agregalo con el Asistente Telegram.")

    for value, name in (
        (media_storage_chat_id, "MEDIA_STORAGE_CHAT_ID"),
        (publish_page_chat_id, "PUBLISH_PAGE_CHAT_ID"),
    ):
        try:
            parsed = int(value.strip() or "0")
        except ValueError:
            errors.append(f"{name} debe ser un ID numérico.")
            continue
        if parsed > 0:
            errors.append(f"{name} debe ser 0 o un ID negativo de Telegram.")

    for value, name, minimum in (
        (human_verification_timeout_seconds, "HUMAN_VERIFICATION_TIMEOUT_SECONDS", 30),
        (human_verification_raid_window_seconds, "HUMAN_VERIFICATION_RAID_WINDOW_SECONDS", 1),
        (human_verification_raid_threshold, "HUMAN_VERIFICATION_RAID_THRESHOLD", 1),
        (human_verification_raid_timeout_seconds, "HUMAN_VERIFICATION_RAID_TIMEOUT_SECONDS", 30),
    ):
        try:
            parsed = int(value.strip() or "0")
        except ValueError:
            errors.append(f"{name} debe ser un entero.")
            continue
        if parsed < minimum:
            errors.append(f"{name} debe ser >= {minimum}.")

    if (
        human_verification_raid_timeout_seconds.strip()
        and human_verification_timeout_seconds.strip()
    ):
        try:
            raid_timeout = int(human_verification_raid_timeout_seconds.strip())
            normal_timeout = int(human_verification_timeout_seconds.strip())
            if raid_timeout > normal_timeout:
                warnings.append(
                    "HUMAN_VERIFICATION_RAID_TIMEOUT_SECONDS supera al TTL normal; "
                    "se usará el menor de ambos."
                )
        except ValueError:
            pass

    if "chie" in bots and not bots["chie"].get("token", "").strip():
        warnings.append("Chie es el bot base de configuración; sin su token no se puede preparar la comunidad.")

    if not authorized and not allow_user_private_chat:
        warnings.append("No hay grupos autorizados y el acceso privado de usuarios está desactivado.")

    return SetupValidation(tuple(errors), tuple(warnings))
