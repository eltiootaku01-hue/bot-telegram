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

Estado actual:
**CLOSED / VERIFIED REPAIR + PASS**

Estado histórico:
**RISK / REQUIRES AUDIT**

El hallazgo histórico señalaba la necesidad de verificar:

- WAL;
- busy_timeout;
- duración de transacciones;
- ownership de conexiones;
- escritura concurrente;
- cierre limpio;
- acceso multi-proceso.

### Cierre verificado

Las líneas de trabajo H05-L02..L09 quedaron validadas como:

**VERIFIED PASS**

La reparación correspondiente fue integrada mediante PR #96 en:

`main@94757b257e9df0be3886fbaf11d66dd421c2c4e3`

La evidencia de cierre es específica de HUESO-05 y conserva el historial del riesgo original. No implica despliegue en producción ni cierre del conjunto global de problemas de salud arquitectónica.

No se observó `database is locked` en los escenarios HUESO-05 verificados. HUESO-10 mantiene su propio gate y estado independiente.

### Estado

HUESO-05 queda cerrado en el registro arquitectónico actual. Cualquier nueva incidencia o afirmación de bloqueo SQLite debe aportar evidencia propia y evaluarse mediante su gate correspondiente.


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

## HUESO 09 — CANCELACIÓN NO PROPAGADA / ZOMBIE TASKS

Estado:
**HYPOTHESIS / HIGH PRIORITY AUDIT**

TaskEngine ya representa cancelación, timeout y lifecycle lógico.

Debe verificarse si esa cancelación alcanza realmente:

- HTTP/LLM calls;
- Playwright;
- WebChat;
- workers;
- subprocesses.

### Riesgo hipotético

Una tarea podría aparecer como CANCELLED mientras una operación física o de red continúa ejecutándose.

### Consecuencias potenciales

- consumo de tokens;
- consumo de CPU;
- procesos huérfanos;
- callbacks tardíos;
- respuestas duplicadas.

### Gate

Demostrar una cadena completa:

`cancel lógico -> cancel físico/I/O -> terminación -> evidencia -> release`

---

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
