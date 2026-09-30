# Arquitectura BOT-IA / Knowledge Engine

```text
Fuentes / Canon
      ↓
Librarian + Retrieval
      ↓
Context Engine
      ↓
Brain / Router
      ↓
Agents / Output Contracts
      ↓
Provider Manager
   ├─ cuenta 1
   ├─ cuenta 2
   ├─ fallback provider
   └─ health + cooldown
      ↓
API del Knowledge Engine
   ├─ Web UI
   ├─ Telegram
   └─ integraciones explícitas (MCP / otras)
```

Principio central: conocimiento, canon, evidencia y reglas de dominio son independientes del modelo. Los providers son adaptadores intercambiables.


## Café Otaku — Character Engine + WebChat compartido (PROPUESTA)

Esta sección describe el diseño aprobado conceptualmente en la auditoría de 2026-09-27. No representa una implementación existente.

    Telegram / Discord / GUI
              ↓
          BOT-IA Core
       ┌──────┼───────────┐
     Identity State      Rules
        │       │           │
     Memory  Economy    Permissions
        │       │           │
        └──────┴────── Events
                        ↓
                 Character Engine
              ┌─────────┴─────────┐
          ROLEPLAY              ANALYSIS
              │                     │
              └──────────┬──────────┘
                         ↓
                 Shared WebChat
               Controller + Queue
                         ↓
              Persistent browser/session
                         ↓
                     Web Chat
                         ↓
                     lenguaje
                         ↓
                 BOT-IA valida
                         ↓
           estado / eventos / publicación

### Principios

- WebChat es un recurso compartido, no propiedad permanente de una personalidad.
- No crear un WebChat separado por personaje o por tarea.
- Las prioridades ordenan tareas pendientes, pero nunca saltan el cooldown del recurso.
- El cooldown es una restricción independiente de prioridad.
- Los estados técnicos no deben aparecer como mensajes visibles al usuario.
- Una interacción directa con Cari debe controlar una intervención pendiente por usuario/personaje, sin bloquear al resto del grupo.
- El Character Engine prepara el contexto; WebChat genera lenguaje.
- BOT-IA conserva autoridad sobre identidad, emociones, relaciones, economía, permisos, inventarios, sesiones, mesas y eventos.
- El modelo no modifica directamente el estado persistente.
- Memoria relevante, mensajes recientes, identidad y contexto de mesa deben mantenerse separados.
- La salida pública debe ser únicamente la voz del personaje; cualquier metadata posterior debe viajar por un contrato separado y no visible.

### Estado actual frente a la propuesta

- src/services/web_queue.py: existe y está conectado al runtime Qt; implementa FIFO y exclusión mutua.
- src/gui/task_orchestrator.py: contiene prioridades HIGH/MEDIUM/LOW, pero no es actualmente la política global del WebChat.
- src/bot_ia/providers/prompt_builder.py: construye roleplay para Tavern, pero todavía no es el Character Engine completo.
- Estado emocional estructurado y actitud operacional: faltantes.
- Selección de memoria relevante para el personaje: faltante.
- Interacción grupal controlada “Hablarle a Cari”: faltante.
- Contrato de metadata emocional posterior: pendiente de diseño.
- Continuidad E2E de sesión compartida: no verificada.

Esta propuesta debe implementarse mediante extensión de infraestructura existente y no mediante un segundo WebChat, una segunda memoria o un segundo sistema de colas sin justificación.

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

Scheduler inicia la tarea lógica en Task Engine antes de entregarla a WebQueue. La señal `ticket_started` sólo confirma que la ejecución física WebChat comenzó y permite actualizar el estado operativo de la camarera.

Cuando llega `ticket_processed`, Tavern primero valida el `task_id`; sólo una respuesta aceptada puede completar y publicar la tarea.

Una respuesta posterior a una cancelación, fallo o completado previo se descarta.

El estado de la camarera permanece BUSY durante una interrupción de tareas internas porque la sesión sigue activa; el retorno de trabajo queda gobernado por TaskEngine para las tareas futuras que utilicen parent/child.


### Correcciones de verificación heredadas

Durante la verificación de FASE 1B, los dos errores de compilación preexistentes de `src/bot/handlers/drop_handler.py` y `src/bot/handlers/support_handler.py` impidieron ejecutar tests.

Se corrigieron únicamente sus literales con saltos de línea para restaurar el código Python válido. No se modificó la lógica funcional de drops, claims ni soporte.

Estas correcciones son de desbloqueo de compilación y no forman parte del diseño del Task Engine.

## Scheduler / Task Routing — FASE actual

Arquitectura operativa:

    TASK ENGINE
         |
         v
    TASK SCHEDULER / ROUTER
       /             \
      /               \
   LOCAL             WEBCHAT
     |                  |
  ejecutor           WebQueue
                        |
                 QWebEngineView

Task Engine es la única autoridad de lifecycle: task_id, estado, deadline, cancelación, interrupción, parent_task_id, validez, wait_reason y return_policy.
Task Scheduler no ejecuta WebChat ni crea una tercera cola. Mantiene un registro de pendientes, aplica HIGH/MEDIUM/LOW, FIFO por prioridad, arbitra recursos y decide cuándo una tarea elegible puede comenzar.
WebQueue continúa siendo el ejecutor físico WebChat. Controla ticket/operation, timeout propio, captura de respuesta, cierre de interacción y exclusión física del navegador.
GUI TaskOrchestrator sigue siendo específico del camino GUI async/legacy. No es el Scheduler global.

### Recursos y concurrencia

Las tareas locales sin resource_key pueden ejecutarse concurrentemente. Una resource_key exclusiva permite serialización sin crear otra instancia del recurso.
WebChat utiliza WEB_MESA_UNICA como clave lógica correspondiente al lock físico _WEB_MESA_UNICA del WebQueue. Significa una sesión física WebChat y una tarea WebChat activa por vez. No representa las futuras mesas sociales del Café.
Cuando el recurso WebChat está ocupado, las tareas WebChat no se duplican en otro navegador: quedan en WAITING con WAITING_WEBCHAT o permanecen pendientes según el punto de entrada.

### Prioridad y starvation

Las prioridades siguen la convención existente: HIGH=1, MEDIUM=2, LOW=3. Dentro de una misma prioridad se conserva FIFO mediante una secuencia monotónica.
Para el único recurso exclusivo actual se aplica una política mínima anti-starvation: después de tres ejecuciones consecutivas de una prioridad superior, se permite seleccionar la tarea de prioridad inferior más antigua que ya sea elegible. No se introduce un sistema de fairness más complejo.

### WAITING

`WAITING_WEBCHAT` y `WAITING_EXTERNAL` representan esperas que pueden volver a ser elegibles cuando el Scheduler detecta que el recurso o dependencia quedó disponible. `WAITING_USER` y `WAITING_TIMER` no se reanudan por un `dispatch()` de rutina: requieren una activación explícita mediante `wake(task_id)`. `INTERRUPTED` tampoco se reanuda automáticamente; el retorno parent/child genera la solicitud explícita que el Scheduler consume.

### Deadlines y cooldown

El Action Deadline pertenece al Task Engine y es absoluto. No se extiende por espera de recursos, timeout de WebQueue, cooldown del circuit breaker ni timers de sesión/mesera.
En el WebQueue actual existen dos tiempos distintos: un retardo de 100 ms antes de reevaluar la cola después de un ticket resuelto, y un circuit cooldown de 10 s después de alcanzar tres fallos consecutivos. Ninguno modifica el deadline de la tarea.
El recurso lógico del Scheduler se libera cuando el ejecutor informa que terminó físicamente mediante execution_finished(task_id), no simplemente cuando el Task Engine cambia a COMPLETED.
Cuando el WebQueue cierra su circuit breaker, emite capacity_restored para despertar al Scheduler. Esto permite que WAITING_WEBCHAT vuelva a ser elegible sin un polling permanente ni una segunda cola.

### Cancelación y respuestas tardías

El Scheduler cancela primero la tarea lógica mediante Task Engine y después solicita la cancelación física al ejecutor si la tarea está activa. Una tarea cancelada no se vuelve a encolar ni se reanima automáticamente.
Las respuestas WebChat se aceptan únicamente mediante task_id. Si la tarea ya está CANCELLED, TIMED_OUT, FAILED, DISCARDED o en otro estado no receptivo, la respuesta se descarta.

### Parent / child y retorno

El Task Engine conserva la decisión de validez mediante can_return(parent_task_id). El Scheduler decide cuándo volver a poner el parent en ejecución.
Separación explícita:
- Task Engine: determina si A sigue siendo válida.
- Scheduler: determina cuándo puede volver A.
- WebQueue: determina si A puede usar ahora la única sesión física WebChat.
El Engine no cambia automáticamente INTERRUPTED -> RUNNING al completar el child. El Scheduler puede registrar el retorno pendiente y esperar a que el ejecutor del parent termine físicamente antes de reanudarlo, evitando doble ejecución.

### Integración

Los tickets de Tavern continúan reutilizando ticket_id como TaskEngine.task_id. La GUI directa WebChat también crea tareas mediante el mismo Engine/Scheduler. operation_id sigue siendo un identificador interno del protocolo de navegador y no sustituye a task_id.
La expiración de una sesión Tavern cancela las tareas vivas asociadas antes de retirar el mapping de tickets, evitando tareas huérfanas que permanezcan válidas después del cierre de la sesión.

### Legacy

src/bot_ia/core/web_queue.py y src/gui/task_orchestrator.py permanecen sin promoción a arquitectura global. No se elimina legacy por esta fase.

### No implementado en esta fase

No se añadieron Café Table, host/invitados, facturación, limpieza, Character Engine, emociones, relaciones, memoria nueva, automatización de Cari, strikes/moderation redesign, nuevos bots, nueva IA, nuevo navegador ni otra WebQueue.
Las esperas `WAITING_USER` y `WAITING_TIMER` no se reanudan automáticamente al llamar `dispatch()`. Requieren una activación explícita mediante el Scheduler (`wake(task_id)`); de este modo una llamada de rutina no convierte una dependencia aún pendiente en trabajo ejecutable. `WAITING_WEBCHAT` y `WAITING_EXTERNAL` sí pueden volver a ser elegibles cuando el recurso/dependencia correspondiente se libera. Un task `INTERRUPTED` tampoco se reanuda por accidente: debe existir una solicitud explícita de retorno, como la generada por la política parent/child.



## Telegram - cierre determinista de recursos de fondo

`TelegramAdapter` posee un `PassiveXPTracker` que mantiene un escritor SQLite en background. El tracker ahora tiene un owner explícito: `TelegramAdapter.close()` libera ese hilo, y `TelegramPoller.stop()` propaga el cierre al adapter. Esto evita que cada adapter creado durante la vida del proceso deje un `nakama-xp-writer` residente.

Durante la auditoría de CI Windows se observaron decenas de esos hilos vivos simultáneamente. El bloqueo posterior aparecía en `Thread.start()` mientras intentaba arrancar el hilo del WebRuntime. El endpoint HTTP no era la causa funcional: WebRuntime pasó de forma aislada en Windows y Ubuntu. La corrección mantiene el flujo real de `/health` y `/openapi.json` y sólo hace explícito el cleanup del recurso que ya existía.

Los tests que crean adapters directamente también registran `close()` como cleanup para que cada caso libere su propio recurso.

## Arquitectura física WebChat — main@1763974 / LAST FUNCTIONAL BASELINE 78d5

La implementación actual separa lifecycle lógico y físico sin sustituir las capas existentes:

```text
RuntimeComponents
      │
      ├── TaskEngine ──→ TaskScheduler
      │                     │
      │                     ▼
      │              WebChatTaskExecutor
      │                     │
      ▼                     ▼
PhysicalLifecycleReconciliation
      │
      ▼
PhysicalWebChatResourceAuthority
      │
   ┌──┴──┐
   ▼     ▼
  QWeb  Playwright
```

### Responsabilidades

- `TaskEngine`: lifecycle lógico y deadlines.
- `TaskScheduler`: scheduling/routing y arbitraje lógico.
- `WebChatTaskExecutor`: adaptación lógica a WebChat.
- `PhysicalLifecycleReconciliation`: binding task/claim/generation, observación lógica y reconciliación física.
- `PhysicalWebChatResourceAuthority`: única fuente de verdad de estado y ownership físico.
- `WebPhysicalIdentity`: identidad Web declarativa no secreta; producción permanece UNKNOWN.
- adapters QWeb/Playwright: integración backend-específica con la Authority.

### Lifecycle

```text
timeout/cancel
   ↓
physical cancellation request
   ↓
termination evidence
   ↓
release OR quarantine
   ↓
reconciliation
```

No existe equivalencia automática `TIMED_OUT → AVAILABLE`, `CANCELLED → AVAILABLE` o `COMPLETED → AVAILABLE`.

### D3 / R10 / S03

`RUNNING + AVAILABLE → DIVERGED`.

`RUNNING + BUSY → TaskEngine.complete() → COMPLETED + BUSY → record_termination(evidence) → COMPLETED + AVAILABLE → ALIGNED`.

### Legacy guard

`src/services/web_queue.py` conserva `_WEB_MESA_UNICA`. Su retiro no está autorizado; la existencia de Authority no prueba equivalencia completa con el ámbito y comportamiento del lock local.

### Provider gate

Los identities productivos de `config/runtime.toml` permanecen con `authentication_state = "UNKNOWN"`. La ejecución física productiva requiere `VERIFIED`.
