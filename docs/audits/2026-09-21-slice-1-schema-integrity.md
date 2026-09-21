# Slice 1 — Esquemas e integridad de persistencia

Fecha: 2026-09-21

## Objetivo

Este slice fija las invariantes que la base de datos debe rechazar por sí misma. Las reglas no dependen de handlers de Telegram ni de un proceso concreto, de modo que futuros adaptadores y el Core Java puedan compartir el mismo contrato persistente.

## Ledger de puntos

La tabla `point_transactions` mantiene:

- importe distinto de cero;
- referencia idempotente con clave única por usuario, comunidad, tipo y referencia;
- par de referencia todo-o-nada: `reference_type` y `reference_id` deben existir juntos o estar ambos vacíos.

Esto evita transacciones semánticamente incompletas y conserva el ledger como fuente auditable de cargos y recompensas.

## Estados económicos y de juego

`game_encounters.status` solo admite:

- `active`
- `captured`
- `expired`
- `cancelled`

`rare_drop_approvals.status` solo admite:

- `pending`
- `approved`
- `rejected`

`trivia_rounds.status` solo admite:

- `active`
- `won`
- `expired`
- `failed`
- `cancelled`

Además, las trivias exigen índice de respuesta no negativo y recompensa positiva.

## Pedidos

`fan_requests.points_cost` no puede ser negativo.

## Compatibilidad de bases existentes

Los esquemas nuevos reciben las restricciones mediante SQLAlchemy `CheckConstraint`.

Para bases SQLite creadas por versiones anteriores, `Database.create_schema()` instala triggers `BEFORE INSERT/UPDATE` equivalentes. La migración es aditiva y no requiere borrar datos existentes.

## Pruebas del contrato

`tests/test_schema_integrity.py` cubre:

- perfiles con valores negativos;
- colecciones inválidas;
- transacciones con importe cero;
- referencias incompletas del ledger;
- estados desconocidos de encuentros;
- estados desconocidos de aprobaciones;
- estados inválidos de trivia;
- índice de respuesta negativo;
- costo negativo de pedidos;
- límites diarios;
- persistencia de triggers después de cerrar y recrear la conexión SQLite.

## Frontera del slice

Este slice no implementa todavía el Core Java ni los DTOs/adaptadores Telegram. El contrato de persistencia queda primero estable y verificable; el siguiente slice podrá consumirlo sin cambiar las invariantes para hacer funcionar una interfaz concreta.
