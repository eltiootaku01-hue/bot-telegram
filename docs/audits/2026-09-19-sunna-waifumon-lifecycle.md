# Auditoría de ciclo de vida de Sunna / WaifuMon

Fecha: 2026-09-19

## Invariantes verificadas

- Un encuentro salvaje activo por comunidad: el esquema mantiene un índice único parcial sobre `game_encounters(chat_id)` para `status = 'active'`.
- Un usuario no puede intentar dos veces el mismo encuentro: `game_attempts` tiene unicidad por `(encounter_id, user_id)`.
- La captura es una transición condicional `active -> captured`; solamente el ganador puede completar el encuentro.
- La recompensa de puntos de captura usa una referencia idempotente `encounter + encounter_id`.
- Las copias/XP de colección se actualizan con expresiones SQL incrementales para evitar pérdidas por carreras.
- La fusión de colección usa una actualización condicional sobre rareza y cantidad de copias.
- Una ronda de trivia activa se reutiliza mientras siga vigente; las rondas vencidas se retiran antes de intentar crear otra.
- El ganador de trivia se reclama mediante `active -> won`; solamente un participante puede ganar.
- Las recompensas de trivia usan una referencia idempotente basada en el ID de la ronda.
- Las decisiones de drops raros son de un solo uso mediante una transición SQL condicionada por `status = 'pending'`.
- La expiración de encuentros salvajes es una transición condicionada por `active` y `expires_at <= now`; no puede sobrescribir `captured`, `won` u otros estados terminales.
- El detector de encuentros salvajes retira registros activos ya vencidos antes de decidir si puede aparecer otro.

## Regresiones añadidas en este ciclo

- `tests/test_rare_approval.py`: una segunda resolución de una aprobación ya decidida no cambia el resultado.
- `tests/test_wild_scheduler.py`: un encuentro capturado no puede ser marcado como expirado y un encuentro activo vencido sí se retira correctamente.
- `tests/test_trivia_service.py`: una ronda vencida no bloquea la creación de la siguiente y una ronda vigente continúa siendo única.

## Límite actual de validación

La integración CI existente ejecuta Ruff + Pytest en Ubuntu para pushes a `main` y pull requests. La construcción Windows ejecuta además pruebas nativas de medios, empaquetado de cinco ejecutables, smoke test de BotManager, instalador Inno Setup, ZIP portable y checksums.

Este documento no sustituye esas ejecuciones: el estado de GitHub Actions debe considerarse la fuente de verdad para la validación final de cada commit.
