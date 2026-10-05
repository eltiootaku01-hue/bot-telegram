# HALLAZGOS DE ARQUITECTURA Y CONCURRENCIA

Fecha de registro:
2026-10-03

Este documento consolida los riesgos arquitectónicos detectados durante la revisión del sistema.

IMPORTANTE:
Estos hallazgos no tienen todos el mismo grado de evidencia. Los que todavía no fueron auditados en código/runtime se mantienen como HYPOTHESIS o RISK.

---

## HUESO 01 — DOS GENERACIONES DE WEBCHAT

Estado:
**VERIFIED ARCHITECTURAL COEXISTENCE / RISK**

Existe una arquitectura física nueva con:

`PhysicalWebChatResourceAuthority`
`PhysicalLifecycleReconciliation`
`QWebPhysicalResourceAdapter`
`PlaywrightPhysicalResourceAdapter`

y todavía existe infraestructura previa como:

`src/services/web_queue.py`
`_WEB_MESA_UNICA`

además de:

`src/bot_ia/core/web_queue.py`

La documentación arquitectónica indica que el legacy no debe retirarse sin demostrar equivalencia.

### Riesgo

Una migración prematura puede crear:

- doble autoridad física;
- doble cola;
- pérdida de exclusividad;
- releases incompatibles;
- divergencia de lifecycle.

### Gate

No retirar legacy hasta demostrar equivalencia física y de lifecycle.

---

## HUESO 02 — DOS CAMINOS DE ARRANQUE

Estado:
**VERIFIED ARCHITECTURAL COEXISTENCE / RISK**

Existe:

`BOT-IA-Core.exe`

y también:

`run_all.py`

`run_all.py` crea procesos independientes para FastAPI, Telegram y Discord.

### Riesgo

Arrancar ambos ecosistemas simultáneamente podría duplicar:

- polling de Telegram;
- acceso a SQLite;
- procesos de WebChat;
- puertos;
- workers;
- estado runtime.

No se afirma que el conflicto exista en la configuración normal. Debe auditarse el ownership de recursos.

### Gate

Definir explícitamente qué componentes pueden coexistir y cuáles son mutuamente excluyentes.

---

## HUESO 03 — QWEBENGINE / CONTEXTO DE EJECUCIÓN

Estado:
**VERIFIED RUNTIME RISK / 2F-8T BLOCKED**

Existe evidencia histórica de problemas QWebEngine en CI, incluyendo errores de carga y fallos de proceso en determinados contextos.

2F-8T permanece bloqueado y no debe utilizarse como excusa para modificar producción sin diagnóstico.

### Riesgo

Una interacción incorrecta entre:

- Qt;
- QWebEngine;
- WebChannel;
- threads;
- pytest;
- lifecycle de páginas/perfiles

puede producir crashes, hangs o estados físicos inconsistentes.

### Gate

Mantener 2F-8T congelado hasta nuevo gate específico.

---

## HUESO 04 — LIFECYCLE DE WORKERS DE TELEGRAM

Estado:
**VERIFIED HISTORICAL RISK / PARTIALLY HARDENED**

El sistema ya documentó problemas relacionados con writers de fondo del PassiveXPTracker y la necesidad de cierre explícito.

Se introdujo cierre explícito mediante `TelegramAdapter.close()` y propagación desde `TelegramPoller.stop()`.

### Riesgo

Si algún path futuro crea adapters/workers sin ownership y cleanup correspondiente:

- quedan hilos vivos;
- aumenta el consumo;
- puede afectar otros workers;
- puede bloquear shutdown.

### Gate

Toda nueva creación de workers debe tener owner y cleanup verificable.

---

## HUESO 05 — SQLITE / MULTIPROCESO

Estado:
**RISK / REQUIRES AUDIT**

Existen varios componentes persistentes y potencialmente múltiples procesos.

### Riesgo

Es necesario verificar:

- WAL;
- busy_timeout;
- duración de transacciones;
- ownership de conexiones;
- escritura concurrente;
- cierre limpio;
- acceso multi-proceso.

No asumir que SQLite está roto.

### Gate

Auditar cada base y cada conexión antes de considerar el ecosistema multi-proceso completamente sano.

---

## HUESO 06 — DOCUMENTACIÓN DESALINEADA

Estado:
**VERIFIED DOCUMENTATION RISK**

Existe documentación con checkpoints históricos que no representan necesariamente el HEAD actual.

Además, documentos arquitectónicos mezclan contenido:

- IMPLEMENTADO;
- PROPUESTO;
- HISTÓRICO;
- PENDIENTE.

### Riesgo

Un Cerebro u Obrero nuevo podría interpretar una propuesta como implementación o un SHA histórico como estado actual.

### Gate

Mantener separación explícita entre estado actual, histórico y propuesta.

---

## HUESO 07 — CONFLICTO QT EVENT LOOP / ASYNCIO

Estado:
**HYPOTHESIS / REQUIRES AUDIT**

El sistema combina Qt/PySide6 con componentes async.

Debe auditarse:

- creación de event loops;
- ownership de loops;
- QThread;
- callbacks;
- señales/slots;
- acceso a widgets desde workers;
- Playwright async;
- servidores HTTP async.

### Riesgo hipotético

Una callback async podría cruzar incorrectamente hacia el thread GUI y provocar:

- race conditions;
- deadlocks;
- hangs;
- crashes nativos.

### No afirmar

No existe evidencia suficiente todavía para declarar que el sistema actual tenga este fallo.

### Gate

Trazar cada frontera GUI ↔ worker ↔ asyncio antes de introducir concurrencia adicional.

---

## HUESO 08 — PYINSTALLER / EXTRACCIÓN ONEFILE

Estado:
**HYPOTHESIS / REQUIRES AUDIT**

La cadena de lanzamiento utiliza ejecutables separados:

`BOT-IA.exe`
`BOT-IA-Core.exe`

Debe verificarse el modo real de empaquetado de cada uno.

### Riesgo hipotético

Si ambos son `--onefile`, pueden existir:

- dos procesos de bootloader;
- dos extracciones temporales;
- mayor coste de arranque;
- restos temporales tras crashes.

### Gate

Auditar los comandos reales de PyInstaller en `build_desktop.ps1` y cualquier spec/config relacionado antes de proponer cambiar a `--onedir`.

No cambiar packaging por hipótesis.

---

## HUESO 09 — CANCELACIÓN / RELEASE SAFETY / TERMINATION EVIDENCE

Estado:
**VERIFIED RELEASE-GATE WEAKNESS**

Existe una debilidad verificada en el contrato de liberación física: las APIs actuales aceptan evidencia como `str` no vacío sin validar su semántica, procedencia o nivel de terminación/saneamiento.

Esto documenta una **contract weakness**. No declara el root cause de un incidente de producción.

### Adjudicación canónica

| Finding | Estado | Prioridad | Qué queda demostrado |
| --- | --- | --- | --- |
| BUG-001 | **VERIFIED BUG** | **P0** | string no vacío puede autorizar release |
| BUG-002 | **PARTIALLY VERIFIED** | **P2** | ventana Authority/Reconciliation |
| BUG-003 | **VERIFIED RISK** | **P1** | reconcile débil puede salir de QUARANTINED |
| BUG-004 | **NOT DEMONSTRATED** | — | no se demostró ataque same-claim/generation |
| BUG-005 | **VERIFIED BUG** | **P1** | parser acepta `#terminado` embebido/citado |

### BUG-001 — VERIFIED BUG

**P0 / BLOCKING RELEASE SAFETY**

Un `str` no vacío proporcionado por el caller puede recorrer:

`non-empty caller-provided string -> confirm_termination() -> release()`

sin una barrera semántica que demuestre termination.

La evidencia demostrada es la debilidad contractual. No se declara que BUG-001 sea el root cause de un incidente de producción.

### BUG-003 — VERIFIED RISK

**P1 / QUARANTINE RELEASE WEAKNESS**

Una autoridad en estado:

`QUARANTINED + arbitrary non-empty evidence -> AVAILABLE`

puede salir de `QUARANTINED` mediante `reconcile()` con evidencia no tipada.

La debilidad demostrada es la **absence of typed sanitation/reconciliation evidence**.

No se afirma que `reconcile()` necesariamente deba exigir un ACK de Gemini.

### BUG-005 — VERIFIED BUG

**P1 / AMBIGUOUS PROTOCOL PARSER**

El marcador:

`#terminado`

puede aparecer embebido o citado dentro del texto y aun así ser encontrado por el parser cuando coinciden bot/ticket actuales.

Esto puede alimentar la debilidad de release descrita en BUG-001.

### BUG-002 — PARTIALLY VERIFIED

**P2 / CONSISTENCY WINDOW**

La Authority puede quedar `AVAILABLE` antes de que Reconciliation escriba `termination_state/release_state CONFIRMED`.

**Security consequence: NOT DEMONSTRATED.**

No se justifica Two-Phase Commit (2PC) a partir de esta evidencia.

### BUG-004 — NOT DEMONSTRATED

La combinación:

`same claim_id + same execution_generation + different operation_id`

no fue demostrada como una secuencia legítima del lifecycle actual.

Por tanto, no se registra como bug confirmado. Como máximo, queda como **DEFENSE-IN-DEPTH CANDIDATE**.

### Contrato conceptual

Debe mantenerse explícitamente la separación:

`OWNERSHIP FENCING`
`≠`
`TERMINATION EVIDENCE`

`OBSERVATION`
`≠`
`RELEASE AUTHORIZATION`

`non-empty string`
`≠`
`semantic termination evidence`

### #terminado

`#terminado` representa **logical protocol closure**.

`#terminado != provider termination proof`

Por sí solo, `#terminado` no debe autorizar physical release. Esta es una propiedad del **contrato futuro**; no significa que la reparación ya esté implementada.

### Quarantine

La propiedad documental futura es:

`CANCELLED_WITHOUT_TERMINATION_EVIDENCE`
`->`
`QUARANTINED`

Debe diferenciarse:

- termination confirmation;
- resource sanitation / reconciliation.

No se prescribe todavía cómo se implementará el saneamiento.

La propiedad de seguridad a preservar es:

`weak UI/protocol evidence`
`must not be sufficient for AVAILABLE`

### Root cause

**NOT DECLARED**

No se registra BUG-001, `#terminado`, QWebEngine ni ningún otro finding como root cause. La documentación distingue **contract weakness** de **incident root cause**.

### 2F-8T

**VERIFIED BLOCKER / ROOT CAUSE UNKNOWN**

**NO REOPENED**

No se introduce ninguna conclusión nueva sobre Qt/QWebEngine.

### Diseño futuro — PROPUESTA

El siguiente diseño queda documentado únicamente como propuesta, no como implementación:

`PhysicalReleaseEvidence`

con dos propósitos:

- `TERMINATION`
- `SANITIZATION`

Campos posibles de diseño futuro:

- `provider`
- `evidence_type`
- `evidence_level`
- `physical_resource_id`
- `claim_id`
- `execution_generation`
- `operation_id`
- `ticket_id`
- `observation`

Todos estos campos son **future design / not implemented**.

BUG-001, BUG-003 y BUG-005 deben converger en un único contrato futuro de evidencia.

### Next gate

**NEXT GATE: HUESO-09-MINIMAL-RELEASE-GATE-DESIGN**

**NO IMPLEMENTATION YET**

**HUESO-09 PROVIDER RUNTIME: BLOCKED**

2F-8T continúa bloqueando el runtime de Gemini.

## HUESO 10 — SQLITE DATABASE LOCK

Estado:
**HYPOTHESIS / HIGH PRIORITY AUDIT**

Debe verificarse si las conexiones SQLite establecen:

- `journal_mode=WAL` cuando corresponde;
- `busy_timeout` adecuado;
- transacciones breves;
- commits previsibles;
- cierre correcto.

### Riesgo hipotético

`database is locked` bajo concurrencia.

### Consecuencias potenciales

- fallos de workers;
- pérdida de operaciones de outbox;
- retry storms;
- inconsistencia temporal.

### Gate

Medir antes de modificar.

No aplicar WAL globalmente sin verificar qué bases y procesos lo necesitan.

---

## HUESO 11 — PROVIDER STARVATION

Estado:
**RISK / REQUIRES AUDIT**

El Provider Manager tiene fallback, health y cooldown.

Debe auditarse si tareas de fondo y tareas interactivas comparten exactamente el mismo presupuesto de:

- requests;
- tokens;
- TPM/RPM;
- concurrencia.

### Riesgo

Trabajo batch podría consumir capacidad y degradar tareas interactivas.

### Gate

Definir si existe prioridad de workload antes de implementar throttling nuevo.

No asumir que el Provider Manager actual sufre starvation sin evidencia.

---

## HUESO 12 — TELEGRAM OUTBOX / SPLIT-BRAIN

Estado:
**RISK / REQUIRES AUDIT**

El outbox ya utiliza estados persistentes, pero debe verificarse la atomicidad real del claim/send/update.

### Preguntas

- ¿dos procesos pueden reclamar el mismo `update_id`?
- ¿qué transacción protege el cambio de estado?
- ¿existe estado PROCESSING o equivalente?
- ¿qué ocurre si el proceso muere entre claim y send?
- ¿cómo se evita enviar dos veces?

### Consecuencia potencial

Duplicación de mensajes si dos runtimes comparten la misma base.

### Gate

Auditar transacciones reales antes de afirmar split-brain.

---

## HUESO 13 — GROWTH DE CONTEXTO / MEMORY PRESSURE

Estado:
**HYPOTHESIS / REQUIRES MEASUREMENT**

Debe verificarse el comportamiento de:

- historial;
- memoria;
- retrieval;
- context builder;
- summarization;
- pruning;
- límites del provider.

### Riesgo hipotético

Ventanas crecientes pueden provocar:

- más tokens;
- más latencia;
- mayor coste;
- errores por límite de contexto.

### Gate

Medir tamaño de contexto real y estrategia de poda antes de rediseñar.

---

## ORDEN DE INVESTIGACIÓN RECOMENDADO

Primero:

1. lifecycle y concurrencia;
2. SQLite/ownership;
3. cancelación física;
4. Qt/asyncio boundaries;
5. packaging;
6. provider scheduling;
7. context growth.

No implementar soluciones masivas de una sola vez.

## REGLA

Un hallazgo solo pasa a CLOSED con evidencia de:

- comportamiento;
- reparación;
- validación;
- ausencia de regresión relevante.
