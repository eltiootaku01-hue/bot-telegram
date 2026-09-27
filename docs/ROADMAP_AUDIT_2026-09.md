# Auditoría progresiva — septiembre de 2026

## Decisiones confirmadas

- Equipo de referencia: Ryzen 5 5600G, 16 GB RAM, GPU integrada.
- Núcleo local-first y determinista.
- SQLite/FTS5 como primera capa de búsqueda local.
- Índices derivados y reconstruibles.
- Embeddings y modelos locales sólo como capacidades opcionales y bajo demanda.
- No convertir memoria, web o API en canon automáticamente.
- Aislamiento obligatorio por universo/proyecto.

## FASE 0.3 — 2026-09-27

Se añadió el registro persistente de la auditoría de requisitos, arquitectura y decisiones:

- `docs/FASE_0_3_AUDITORIA_REQUISITOS_ARQUITECTURA_DECISIONES_2026-09-27.md`
- HEAD de referencia de la auditoría: `4f2141759483a3f8f3e3610e3b3cad8d1ec2f314`
- Estado: auditoría + diseño, sin cambios funcionales.
- Se documentó la diferencia entre el runtime actual basado en ProviderManager y el objetivo confirmado de conversación de personajes mediante chat web.
- Se documentaron los huecos de Tavern Telegram, estados de mesera, espera por regreso, TCG inventory/deck, rental fallback, MatchHistory, economía, identidad, WebQueue, Chromium, ProviderManager, Ollama, memoria, emociones, timing, almacenamiento externo y TCG Web.
- Las decisiones aún no confirmadas quedan marcadas como `DECISIÓN PENDIENTE DEL USUARIO`.



## Actualización de diseño — Character Engine + WebChat compartido (2026-09-27)

Se incorpora como requisito arquitectónico, todavía no implementado:

- WebChat como recurso compartido para tareas que requieren generación de lenguaje.
- Cola con prioridades conceptuales y cooldown independiente de prioridad.
- Estados técnicos internos separados de cualquier mensaje visible al usuario.
- Interacción controlada de una sola intervención por usuario/personaje cuando se hable directamente con Cari.
- Character Engine como ensamblador de contexto antes de WebChat.
- Separación de roleplay y análisis.
- Estado emocional y actitud proporcionados por BOT-IA.
- Selección de memoria relevante en vez de enviar todo el historial.
- Posibilidad de ambigüedad y contrapregunta natural.
- Salida pública limitada al diálogo del personaje.
- Metadata emocional posterior separada del texto público.

### Conflictos documentados

- src/services/web_queue.py es FIFO + exclusión mutua; no demuestra prioridad global actual.
- src/gui/task_orchestrator.py tiene HIGH/MEDIUM/LOW, pero no es la cola global del runtime Qt normal.
- src/bot_ia/providers/prompt_builder.py implementa roleplay de Tavern, pero no el Character Engine completo.
- No existe todavía estado emocional persistente estructurado.
- No existe todavía actitud operacional persistente.
- No existe selección especializada de memoria para Character Engine.
- No existe flujo grupal “Hablarle a Cari” con la restricción especificada.
- El mecanismo de señal/metadata emocional posterior todavía requiere contrato técnico.

### Política

Esta actualización es documentación de diseño. No autoriza implementación funcional, migración de runtime, cambio de dependencias ni eliminación de legacy.

## FASE 1 — Seguridad y autoridad (implementación)

Implementada una autoridad de acceso pequeña y reutilizable en src/bot_ia/security/authority.py.

- IDs estables de SuperAdmin Telegram/Discord: IMPLEMENTADO.
- TELEGRAM_ADMIN_USER_IDS centralizado: IMPLEMENTADO.
- AUTHORIZED_GROUP_ID / TELEGRAM_OFFICIAL_CHAT_IDS: REUTILIZADOS.
- AUTHORIZED_FORUM_ID: REUTILIZADO.
- DISCORD_AUTHORIZED_GUILD_IDS: IMPLEMENTADO, fail-closed.
- /setup_group y callbacks administrativos Telegram: GUARDADOS POR AUTORIDAD.
- Moderación automatizada Discord: limitada a guild autorizada.
- TCG Discord /drop y claim: limitados a guild autorizada.
- Character Engine, prompts privados y detector de extracción: PENDIENTE.
- GUI local: REUTILIZADA; autenticación OS formal: PENDIENTE.

### Verificación

Se añadió tests/test_security_authority.py con 18 pruebas contractuales para identidad, grupos/topics, guilds, privilegios y exposición de secretos.

En el punto de partida existían errores de sintaxis ajenos a FASE 1 en:
- src/bot/handlers/drop_handler.py
- src/bot/handlers/support_handler.py
- src/discord/bot.py

El error de sintaxis de src/discord/bot.py se corrigió únicamente porque ese archivo debía modificarse para aplicar el guard de guild. Los dos fallos restantes siguen fuera del alcance de FASE 1.

No se añadieron dependencias ni migraciones SQLite.
## FASE 1B — Task Engine + tiempos + espera (IMPLEMENTACIÓN)

Se añade `src/bot_ia/core/task_engine.py` como contrato común de ciclo de vida. Es deliberadamente un motor de estado, no una cola ni un ejecutor WebChat.

### Separación de responsabilidades

```
Task Engine
  ├─ task_id / identidad de tarea
  ├─ estado
  ├─ deadline / timeout policy
  ├─ cancelación / interrupción
  ├─ parent_task_id
  └─ return policy
          │
          └── WebQueue existente
                ├─ ticket_id (reutilizado como task_id en Tavern)
                ├─ operation_id
                └─ automatización del navegador
```

La cola de `src/services/web_queue.py` no fue reemplazada ni convertida en scheduler global. Su `operation_id` continúa siendo un mecanismo específico de WebChat para invalidar callbacks de navegador. El `TaskEngine` es la autoridad sobre si una tarea sigue válida.

`gui/task_orchestrator.py` continúa siendo un orquestador async específico de GUI. No se promovió a cola global ni se fusionó a ciegas.

`src/bot_ia/core/web_queue.py` sigue tratado como infraestructura legacy/condicionada por versión y no fue incorporado al nuevo motor.

### Contrato de tarea

Los campos implementados son los solicitados por la fase: `task_id`, `requester`, `task_type`, `context`, `priority`, `state`, `created_at`, `started_at`, `deadline`, `timeout_policy`, `parent_task_id`, `interrupted_by` y `return_policy`. Se añadió `wait_reason` porque es necesario para representar de forma explícita por qué una tarea está en WAITING.

La prioridad se almacena como entero con la misma convención ya usada por la prioridad GUI: HIGH=1, MEDIUM=2, LOW=3. No se importó el enum de GUI al núcleo para evitar acoplamiento Core→GUI.

### Espera

`WAITING` representa una tarea todavía viva. Las razones admitidas son USER, EXTERNAL, WEBCHAT y TIMER.

Los estados técnicos no se exponen directamente a Telegram/Discord.

### Cancelación y respuestas tardías

`validate_response(task_id)` sólo acepta respuestas cuando la tarea está en RUNNING o WAITING y su deadline no venció.

Una tarea CANCELLED, TIMED_OUT, FAILED, DISCARDED o INTERRUPTED no puede aceptar directamente una respuesta WebChat.

Esto garantiza que una respuesta tardía identificada por `task_id` no modifique ni publique estado de otra tarea.

### Parent y retorno

Cuando una tarea hija con `parent_task_id` comienza, el parent RUNNING/WAITING pasa a INTERRUPTED.

Al completar la hija:
- RETURN_IF_VALID reanuda el parent sólo si sigue válido;
- DISCARD_PARENT invalida el parent;
- NO_RETURN deja el parent interrumpido.

La validez del parent incluye comprobar el deadline antes de reanudarlo.

### Integración con WaitressSessionManager

No se reemplazan ACTIVE_SESSIONS, BUSY, RESTING ni sus timers.

Los tickets de Tavern reutilizan su `ticket_id` existente como `TaskEngine.task_id`. La sesión sigue siendo responsable de su propio tiempo de sesión y descanso; el Action Deadline del Task Engine permanece conceptualmente separado y no se deriva de esos tiempos.

Cuando WebQueue notifica `ticket_started`, Tavern inicia la tarea.

Cuando llega `ticket_processed`, Tavern primero valida el `task_id`; sólo una respuesta aceptada puede completar y publicar la tarea.

Una respuesta posterior a una cancelación, fallo o completado previo se descarta.

El estado de la camarera permanece BUSY durante una interrupción de tareas internas porque la sesión sigue activa; el retorno de trabajo queda gobernado por TaskEngine para las tareas futuras que utilicen parent/child.


### Correcciones de verificación heredadas

Durante la verificación de FASE 1B, los dos errores de compilación preexistentes de `src/bot/handlers/drop_handler.py` y `src/bot/handlers/support_handler.py` impidieron ejecutar tests.

Se corrigieron únicamente sus literales con saltos de línea para restaurar el código Python válido. No se modificó la lógica funcional de drops, claims ni soporte.

Estas correcciones son de desbloqueo de compilación y no forman parte del diseño del Task Engine.

### Dependencia de verificación descubierta durante FASE 1B

La primera ejecución posterior a la corrección de sintaxis alcanzó `pytest`, pero la colección se detuvo porque CI no instalaba `SQLAlchemy`, pese a que el repositorio ya importa SQLAlchemy en código y pruebas.

Por tratarse de una dependencia de runtime existente que impedía verificar el repositorio completo, se declaró `SQLAlchemy>=2.0,<3` en `pyproject.toml` y se añadió a la instalación explícita del workflow CI.

Esta modificación no pertenece al Task Engine funcional; es una corrección mínima del contrato de dependencias/CI necesaria para poder probar la fase y la base existente.
