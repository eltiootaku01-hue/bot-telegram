# Auditoría cruzada de arquitectura — 2026-09-16

## Alcance

Revisión cruzada de `main` combinando:

- estado real del repositorio y su historial;
- documentación oficial de SQLAlchemy, aiogram, Telegram Bot API y GitHub Actions;
- comparación de arquitecturas públicas de bots aiogram;
- evidencia de CI posterior al último cambio.

El objetivo es detectar riesgos de arquitectura, no aumentar artificialmente porcentajes de avance.

## Resultado de CI

El commit `eb426386d90a70a36ab288e590fddc097e0923d6` (`docs: deepen transaction boundary audit`) tiene una ejecución CI de GitHub Actions `35140299857` concluida con `success` el 2026-09-16.

Esto confirma que el pipeline configurado actualmente pasa para el SHA actual de `main`. No se debe extrapolar este resultado a futuros commits sin una nueva ejecución.

## Hallazgo principal: propiedad de transacciones

`app/services/requests.py` recibe un `AsyncSession` desde el exterior, pero `RequestService.create_paid()` ejecuta `commit()` y `rollback()` internamente. El flujo es funcional, pero la frontera transaccional queda repartida entre el servicio y su llamador.

La documentación oficial de SQLAlchemy 2.1 establece que `AsyncSession` representa una transacción con estado y no debe compartirse entre tareas concurrentes; para concurrencia se recomienda una sesión separada por tarea. La misma documentación sirve como criterio para mantener una unidad de trabajo claramente delimitada.

Conclusión de auditoría: no conviene eliminar commits de forma mecánica. La próxima corrección debe introducir una frontera atómica local (por ejemplo, savepoint/unidad de trabajo apropiada) para que un cobro insuficiente o una carrera de idempotencia no dejen residuos, mientras el commit final siga perteneciendo a la frontera superior cuando corresponda.

## Hallazgo de concurrencia pendiente

`FanRequest.source_message_id` y las referencias de `PointTransaction` ya se usan para idempotencia. El siguiente nivel de evidencia que falta es una prueba de integración con dos operaciones concurrentes sobre el mismo mensaje/referencia.

La prueba debe verificar simultáneamente:

1. como máximo una solicitud efectiva;
2. como máximo un cargo efectivo;
3. que el saldo final se descuenta una sola vez;
4. que una segunda entrega duplicada devuelve el estado existente sin crear otro cargo.

No se considera cerrado con una prueba secuencial, porque la carrera relevante ocurre entre las comprobaciones previas y la restricción única de la base.

## Comparación externa

### aiogram

El propio proyecto aiogram organiza su framework alrededor de routers, middleware, filtros y composición asíncrona. Esto coincide con el uso del proyecto de módulos y handlers como transporte, dejando la lógica de dominio fuera del adaptador de Telegram.

### aiogram3-uow-taskiq-skeleton

Este proyecto público separa explícitamente handlers, servicios y repositorios y utiliza Unit of Work para encapsular transacciones. Es una referencia útil para la frontera transaccional, pero su infraestructura está orientada a PostgreSQL/Redis/Taskiq y no debe copiarse sin necesidad.

### telegram-bot-template-v2

Este proyecto separa bot, servicios, middlewares y persistencia y documenta explícitamente Repository + Unit of Work, además de observabilidad. Confirma que estas fronteras son patrones habituales en bots complejos.

### Diferencia deliberada de este proyecto

El proyecto actual necesita además una capa de dominio de personajes, repertorio authored-only, mundo, rutinas y operador humano. Por ello, una arquitectura genérica de bot no cubre por sí sola la finalidad de Ciudad Animals. La comparación se utiliza como control de arquitectura, no como sustitución del diseño propio.

## Telegram y deduplicación

La documentación oficial de Telegram indica que `update_id` es un identificador único que aumenta secuencialmente y resulta útil para ignorar actualizaciones repetidas o restaurar el orden. Esto debe considerarse en una futura auditoría del transporte y de la idempotencia global.

La deduplicación por `source_message_id` de solicitudes es de dominio y no sustituye necesariamente una estrategia de transporte basada en `update_id` si el sistema necesita garantizar procesamiento exactamente una vez a nivel de update.

## GitHub Actions

GitHub Actions permite concurrencia por defecto y ofrece `concurrency` para limitar ejecuciones o cancelar ejecuciones obsoletas. La auditoría no recomienda añadirlo automáticamente: primero debe observarse si el repositorio genera ejecuciones redundantes o conflictos reales. En un proyecto cuyo objetivo es auditar cada cambio, cancelar indiscriminadamente ejecuciones puede ocultar evidencia útil.

## Decisiones de esta auditoría

- Mantener CI como evidencia obligatoria después de cada cambio relevante.
- No cambiar la arquitectura a Clean Architecture/UoW solo por comparación externa.
- Priorizar la corrección de propiedad transaccional de solicitudes.
- Añadir primero la prueba concurrente de solicitudes/puntos.
- Auditar después los recorridos de WaifuMon, Trivia y Media con el mismo criterio `Telegram → módulo → servicio de dominio → persistencia → evento/mundo`.
- Revisar posteriormente la deduplicación del transporte Telegram con `update_id`.
- Mantener la IA como componente opcional y subordinado a las reglas del dominio.

## Fuentes consultadas

- SQLAlchemy 2.1 — AsyncIO / AsyncSession: https://docs.sqlalchemy.org/en/21/orm/extensions/asyncio.html
- Telegram Bot API — Update / getUpdates: https://core.telegram.org/bots/api
- GitHub Actions — Concurrency: https://docs.github.com/en/actions/concepts/workflows-and-actions/concurrency
- aiogram — documentación y repositorio oficial: https://docs.aiogram.dev/ y https://github.com/aiogram/aiogram
- Comparación pública: PyDevDeep/aiogram3-uow-taskiq-skeleton
- Comparación pública: Glour/telegram-bot-template-v2
