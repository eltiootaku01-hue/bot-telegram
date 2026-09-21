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

## Estados de juego

`game_encounters.status` admite únicamente:

- `active`
- `captured`
- `closed`
- `expired`
- `cancelled`

`rare_drop_approvals.status` admite únicamente:

- `pending`
- `approved`
- `rejected`

`trivia_rounds.status` admite únicamente:

- `active`
- `publishing`
- `won`
- `expired`
- `failed`
- `delivery_unknown`
- `cancelled`

Los estados adicionales de publicación/entrega son deliberados: permiten representar una operación cuyo envío a Telegram todavía necesita confirmación sin falsear el estado durable.

Las trivias exigen además índice de respuesta no negativo y recompensa positiva.

## Pedidos

`fan_requests.points_cost` no puede ser negativo.

## Compatibilidad de SQLite

Los esquemas nuevos reciben las restricciones mediante SQLAlchemy `CheckConstraint`.

Para SQLite ya creado por versiones anteriores, `Database.create_schema()` mantiene triggers equivalentes `BEFORE INSERT/UPDATE`.

Los triggers se eliminan y recrean durante cada inicialización del esquema. Esto es intencional: permite que una base antigua reciba una definición de invariante actualizada cuando se agregan estados legítimos nuevos, evitando dejar reglas obsoletas persistidas en el archivo SQLite.

La actualización es aditiva respecto de los datos y no requiere eliminar las tablas existentes.

## Índices de concurrencia

El esquema conserva restricciones únicas para los puntos sensibles:

- un encuentro salvaje activo por comunidad;
- una ronda de trivia activa por comunidad;
- una sola referencia durable para cada transacción de puntos;
- una sola solicitud por mensaje fuente cuando existe `source_message_id`.

Estas restricciones son parte del contrato de concurrencia, no optimizaciones opcionales.

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
- persistencia de triggers después de cerrar y recrear la conexión SQLite;
- rechazo de una referencia incompleta también después de reinicializar una base antigua.

## Packaging relacionado

El sistema Windows mantiene el runtime Java en un área de staging separada de PyInstaller (`build\\waifumon-runtime`) y lo copia a `dist\\engine` solamente después de construir los ejecutables. Esto evita que la limpieza/reescritura de salidas de PyInstaller elimine el JRE embebido.

El pipeline Windows valida posteriormente el JAR, `java.exe`, ejecutables, assets, cartas, BotManager, instalador, ZIP portable y checksums.

## Frontera del slice

Este slice establece y valida exclusivamente el contrato durable de persistencia. El Core Java y los adaptadores Python/Telegram ya existen en el repositorio y son compilados por CI, pero la migración de nuevas reglas de negocio hacia la autoridad Java se considera Slice 2.

## Validación de cierre

CI debe completar:

1. Maven/JUnit del engine Java;
2. Ruff;
3. Pytest completo.

Windows debe completar:

1. build del engine y runtime Java;
2. verificación de assets/cartas;
3. verificación de ejecutables;
4. smoke test de BotManager;
5. instalador;
6. ZIP portable;
7. checksums.

El SHA del commit que cierre el slice será la única referencia de estado final.
