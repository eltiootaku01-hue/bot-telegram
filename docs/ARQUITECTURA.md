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

Cuando WebQueue notifica `ticket_started`, Tavern inicia la tarea.

Cuando llega `ticket_processed`, Tavern primero valida el `task_id`; sólo una respuesta aceptada puede completar y publicar la tarea.

Una respuesta posterior a una cancelación, fallo o completado previo se descarta.

El estado de la camarera permanece BUSY durante una interrupción de tareas internas porque la sesión sigue activa; el retorno de trabajo queda gobernado por TaskEngine para las tareas futuras que utilicen parent/child.

