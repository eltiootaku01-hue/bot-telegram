# Auditoría — migración del gameplay de WaifuMon a Java

Fecha: 2026-09-21

## Objetivo

Convertir el motor Java en la única autoridad de las reglas de gameplay migradas, manteniendo Telegram/aiogram como adaptador y SQLite como persistencia durable del estado.

## Riesgos revisados

- dos motores calculando la misma regla;
- divergencia Python/Java;
- contrato ambiguo entre runtimes;
- callbacks que repiten una operación;
- claves de idempotencia reutilizadas con otro payload;
- engine dependiente de Telegram;
- acceso del cliente Java a SQLite;
- runtime Java ausente del instalador;
- JAR eliminado accidentalmente durante el build;
- compilación Java no cubierta por CI;
- contrato `camelCase` distinto del contrato documentado en `snake_case`.

## Decisiones implementadas

### Autoridad

Java contiene actualmente las fórmulas migradas de:

- gacha D/C/B/A/S/SS/SSS;
- combate;
- progresión de nivel, experiencia y etapa.

Python conserva:

- validación de inputs Telegram;
- orquestación de servicios;
- persistencia;
- ledger e idempotencia durable;
- presentación.

`app/game/engine.py` pasó a ser una fachada de compatibilidad.

### Contrato

Versión actual: `1.0`.

Transporte: NDJSON por stdin/stdout.

Campos externos en `snake_case`:

- `contract_version`
- `request_id`
- `correlation_id`
- `player_id`
- `community_id`
- `command`
- `payload`
- `idempotency_key`

La respuesta expone:

- `request_id`
- `success`
- `result_type`
- `payload`
- `state_version`
- `event_ids`
- `reward_ids`
- `error_code`
- `error_message`

### Idempotencia

Java conserva temporalmente respuestas por `idempotency_key` dentro del proceso y devuelve `IDEMPOTENCY_CONFLICT` si una clave se reutiliza con otra operación/payload.

La idempotencia durable continúa en SQLite. El engine Java no sustituye el ledger ni las restricciones de base de datos.

### Packaging

El build Windows:

1. construye el JAR Java;
2. genera un JRE reducido con `jlink`;
3. preserva ambos bajo `dist/engine`;
4. construye BotManager y los cinco presenter bots;
5. verifica el JAR y `java.exe`;
6. incluye el runtime Java en el instalador y ZIP.

Se corrigió un riesgo real donde el launcher limpiaba `dist` después de generar el engine y lo borraba.

## Archivos principales

- `engine/waifumon/pom.xml`
- `engine/waifumon/src/main/java/com/eltiootaku01/waifumon/WaifuMonRuleEngine.java`
- `engine/waifumon/src/main/java/com/eltiootaku01/waifumon/contract/EngineRequest.java`
- `engine/waifumon/src/main/java/com/eltiootaku01/waifumon/contract/EngineResponse.java`
- `app/game/java_engine.py`
- `app/game/engine.py`
- `app/game/progression.py`
- `tools/build_waifumon.bat`
- `tools/build_launcher.bat`
- `.github/workflows/ci.yml`
- `.github/workflows/windows-build.yml`
- `installer/bot-telegram.iss`

## Regresiones

Java/JUnit:

- validación de contrato;
- gacha determinista;
- combate determinista;
- progresión;
- replay por idempotencia;
- conflicto de idempotencia;
- serialización `snake_case`.

Python:

- bridge Python → Java;
- gacha;
- combate;
- progresión;
- persistencia existente.

## Estado de validación

El primer CI de Java encontró un fallo de sintaxis en `ProtocolSmokeTest`; se corrigió inmediatamente. La ejecución siguiente debe ser la referencia de validación del estado actual.

La construcción Windows debe comprobar también el JAR y el JRE bundled.

## Riesgos pendientes

- la autoridad Java todavía no cubre todas las reglas de WaifuMon;
- stats/potential siguen calculándose en Python;
- fusiones, encuentros, misiones, Detector, regalos y cartas no están todavía migrados;
- `state_version` es todavía un placeholder semántico de contrato (valor actual 0) y debe convertirse en versión durable del estado;
- la persistencia sigue siendo responsabilidad Python;
- no existe todavía una API local autenticada para clientes externos/JavaFX;
- el bridge actual usa I/O síncrono de proceso y debe envolverse para no bloquear event loops cuando el engine crezca.

## Siguiente auditoría

Migrar y validar **stats/potential + fusión/evolución**, empezando por eliminar cualquier fórmula duplicada y estableciendo un DTO de estadísticas versionado.

## Bitácora

Este documento registra el ciclo de migración y sus controles. Cada nueva regla migrada debe añadir sus pruebas Java y la regresión Python correspondiente antes de convertirse en autoridad oficial.
