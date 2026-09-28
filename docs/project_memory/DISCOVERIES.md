# Project Memory — Discoveries

## [TESTED] Task Contract

El contrato de tarea existe en `src/bot_ia/supervisor/task_contract.py` y contiene modelo, prioridades, estados, wait reasons, return policies, resultados y referencias contractuales.

## [TESTED] State Machine

Las transiciones válidas e inválidas son evaluables mediante `can_transition` y `transition`. Los estados terminales no tienen transiciones salientes.

## [TESTED] Wait reasons

WAITING requiere uno de: WAITING_USER, WAITING_EXTERNAL, WAITING_WEBCHAT o WAITING_TIMER.

## [TESTED] Parent/child

Se rechazan parent inexistente, self-parent, parent terminal y ciclos detectables en la cadena de parent_task_id.

## [TESTED] Late responses

Solo RUNNING y WAITING aceptan respuestas contractualmente. Unknown y terminal se descartan. Adjuntar resultado a una tarea terminal falla.

## [TESTED] Scope reference

Un scope_id no puede introducirse sin un ScopeLock válido. Si se proporciona ScopeLock, su task_id debe coincidir con el task_id de la tarea.

## [OBSERVED] Diferencia con runtime existente

El TaskEngine existente posee reglas operativas adicionales y no debe modificarse en esta fase. La reconciliación mediante adapter permanece pendiente.

## [UNKNOWN] Persistencia

El Task Contract es actualmente un registro en memoria. No existe persistencia independiente de Tasks implementada por esta fase.

## [UNKNOWN] Integración física

No existe todavía integración Supervisor → TaskEngine ni Supervisor → Scheduler.
