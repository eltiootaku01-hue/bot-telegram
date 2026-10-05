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

---

## HUESO-09 — MINIMAL RELEASE GATE DESIGN

STATUS:
**PROPOSED / NOT IMPLEMENTED**

Este diseño deriva exclusivamente de la adjudicación HUESO-09 ya persistida y de la auditoría del código existente en main.

**REGLA DE ALCANCE:** esta sección define contrato y gates futuros. No cambia src/, tests/, workflows ni el runtime.

### Auditoría de implementación actual

Los cuatro componentes solicitados fueron inspeccionados:

- src/bot_ia/core/physical_resource_authority.py
- src/bot_ia/core/physical_lifecycle_reconciliation.py
- src/services/qweb_physical_resource_adapter.py
- src/services/web_queue.py

También se inspeccionó el adapter Playwright porque constituye un caller adicional relevante del mismo contrato físico:

- src/services/playwright_physical_resource_adapter.py

Hallazgos de contrato observables:

1. PhysicalWebChatResourceAuthority.release(claim) no recibe evidencia semántica; la liberación efectiva depende de que una capa superior acepte la evidencia suministrada.
2. QWeb confirm_termination(execution, evidence: str) solo valida que la cadena no esté vacía y después llama a authority.release().
3. Playwright usa el mismo patrón: confirm_termination(..., evidence: str) acepta cualquier cadena no vacía y llama a authority.release().
4. PhysicalLifecycleReconciliation.record_termination(..., evidence: str) solo exige una cadena no vacía y delega al adapter.
5. En QWeb, la ruta normal es: RESPONSE_COMPLETE -> _extract_terminated() -> terminated_received -> _finish_current() -> record_termination("QWeb #terminado observed").
6. En Playwright, execute_task() llama a confirm_termination(..., "PLAYWRIGHT_TASK_COMPLETED") después de process_task(), sin una prueba provider-specific de estado terminal.
7. Playwright shutdown() también puede pasar una cadena externa como termination_evidence y conducirla a confirm_termination().
8. QWeb release_claim() y Playwright release_claim() son rutas distintas para liberar una reclamación que no llegó a ejecución física; no deben confundirse con evidencia de termination.
9. La autoridad ya comprueba physical_resource_id, claim_id y execution_generation para ownership/current-generation, pero no convierte esos checks en evidencia de termination.
10. reconcile() de la Authority puede pasar de QUARANTINED a AVAILABLE con una cadena no vacía; la debilidad es estructural y no requiere demostrar que un ACK de Gemini deba ser obligatorio.
11. reconcile_task() de Reconciliation observa y actualiza metadata sin liberar; record_termination() es el camino que actualmente convierte la evidencia string en release.
12. En QWeb, cancelOperation() invalida callbacks locales y después el worker lleva el recurso a quarantine; esto no demuestra termination física.
13. En shutdown, QWeb lleva a quarantine si no existe evidencia de termination; libera únicamente la guarda local _WEB_MESA_UNICA, no la claim física.

**Límite de evidencia:** el code-search endpoint del conector no devolvió resultados utilizables para los nombres de caller solicitados y el entorno no permite un git grep local contra GitHub. Por ello, la afirmación se limita a los callers directos observados en los archivos auditados y al adapter Playwright adicional, sin presentar una exhaustividad que no pueda demostrarse.

### Reconstrucción de paths actuales

| Path | Caller / cadena observada | Evidence source actual | Identity disponible | Validación actual | State before -> after | Quién termina autorizando release | Provider termination demostrado |
| --- | --- | --- | --- | --- | --- | --- | --- |
| NORMAL COMPLETION (QWeb) | _consume_response -> _extract_terminated -> terminated_received -> _finish_current -> record_termination | texto del response + match #terminado | ticket, operation_id local, physical execution tuple | ticket/operation callback fence + current claim/generation; parser solo bot/ticket | BUSY -> AVAILABLE | QWeb adapter -> Authority.release | **NO** |
| NORMAL COMPLETION (Playwright) | execute_task -> confirm_termination | string fija PLAYWRIGHT_TASK_COMPLETED | resource/claim/generation/ticket/operation | current execution | BUSY -> AVAILABLE | Playwright adapter -> Authority.release | **NO** |
| CANCEL | _cancel_current / Playwright cancellation | cancel request + weak diagnostic text | current execution | current generation/claim antes de quarantine | BUSY -> CANCELLING -> QUARANTINED | **Ninguno** mientras no exista trusted evidence | **NO** |
| BACKEND FAILURE | _fail_current / Playwright exception | error text | current execution cuando existe | current execution check + quarantine | BUSY/CANCELLING -> QUARANTINED | **Ninguno** mientras no exista trusted evidence | **NO** |
| QUARANTINE | record_quarantine / authority.quarantine / authority.reconcile | reason/evidence strings | physical resource + current claim cuando aplica | quarantine state; reconcile() solo exige string no vacía | QUARANTINED -> AVAILABLE en reconcile() actual | Authority.reconcile | **NO** |
| RECONCILIATION | reconcile_task() | snapshot actual | resource/claim/generation del record | _assert_current_generation | metadata only; no release | no release | **NO** |
| SHUTDOWN | QWeb stop(); Playwright shutdown() | absence/presence de termination evidence | current execution cuando existe | QWeb quarantine path; Playwright acepta string no vacía | ACTIVE -> QUARANTINED o, en Playwright con evidence string y close sin error, AVAILABLE | Playwright adapter -> Authority.release cuando se pasa evidence | **NO** |

La separación normativa futura debe ser:

logical completion
!=
physical termination
!=
sanitization
!=
authority release

### Contrato mínimo futuro: PhysicalReleaseEvidence

PhysicalReleaseEvidence se define como **input tipado de admisión**, no como autorización por sí mismo.

Propósitos permitidos:

- TERMINATION
- SANITIZATION

| Campo | Requiredness | Naturaleza | Regla de confianza futura |
| --- | --- | --- | --- |
| provider | REQUIRED | DERIVED | derivado de la identidad/provider binding; no libre para el caller |
| evidence_type | REQUIRED | TRUSTED / TYPED | enum cerrado: TERMINATION o SANITIZATION; nunca cadena arbitraria |
| evidence_level | REQUIRED | TRUSTED AFTER VERIFICATION | clasificación realizada por la capa verificadora; la Authority consume niveles definidos por contrato, no semántica de Gemini |
| physical_resource_id | REQUIRED para release físico | DERIVED | debe coincidir con el recurso actual; nunca elegir otro recurso desde la evidencia |
| claim_id | CONDITIONAL, requerido para ejecución activa | DERIVED | debe provenir del current claim; mismatch => reject |
| execution_generation | CONDITIONAL, requerido para ejecución activa | DERIVED | debe coincidir con la generación vigente; stale => reject |
| operation_id | CONDITIONAL | DERIVED / CORRELATED | se exige en adapters/eventos donde forme parte del fence; mismatch => reject; no es prueba semántica por sí solo |
| ticket_id | CONDITIONAL | DERIVED / CORRELATED | correlación con el execution/ticket vigente; no es una autoridad de fencing por sí solo |
| observation | OPTIONAL | UNTRUSTED | puede conservar texto/estado bruto para auditoría; nunca autoriza release por sí misma |

**Nota de identidad:** physical_resource_id, claim_id y execution_generation deben tratarse como valores derivados de la ejecución/claim actual, no como campos que un caller cualquiera pueda escoger libremente. operation_id y ticket_id refuerzan correlación, pero no sustituyen la identidad física ni la semántica de termination.

### Trust boundary

La transformación conceptual debe ser:

UNTRUSTED OBSERVATION
->
provider-specific verifier / adapter
->
PhysicalReleaseEvidence
->
lifecycle/current-generation validation
->
release admission
->
AVAILABLE

La capa provider-specific es responsable de decidir si una observación realmente representa el evento físico que el contrato denomina termination o sanitization.

La Authority genérica **no** debe conocer:

- Gemini;
- #terminado;
- DOM;
- QWebEngine;
- Playwright;
- selectors.

La Authority solo debe validar el contrato backend-neutral: identidad, fencing, estado permitido, tipo de evidencia y nivel de evidencia admitido.

**Principio:** PhysicalReleaseEvidence no equivale automáticamente a Trusted Release Authorization. La autorización aparece solo cuando la evidencia tipada atraviesa el gate de admisión con identidad y contexto válidos.

### Release admission futuro

La puerta conceptual deja de ser:

non-empty string -> confirm_termination() -> release()

y pasa a ser:

typed evidence + current binding + admissible evidence level -> release admission

confirm_termination() futuro debe aceptar únicamente evidencia typed TERMINATION que:

1. pertenezca al physical_resource_id actual;
2. coincida con claim_id y execution_generation actuales cuando exista ejecución activa;
3. cumpla operation_id cuando ese campo sea parte del fence del evento;
4. use el provider derivado del binding, no uno libre;
5. posea un evidence_level suficiente para termination;
6. no sea solo observation;
7. no sea un resultado del parser ni una cadena vacía/arbitraria.

Debe rechazar conceptualmente:

- cualquier str arbitraria;
- evidencia vacía;
- #terminado como prueba física;
- texto observado sin verificación;
- DOM mutation;
- desaparición del stop button;
- reaparición del send button;
- silencio temporal;
- callback invalidation;
- logical cancellation;
- local timeout.

Ninguna de esas señales debe etiquetarse como provider ACK sin evidencia runtime correspondiente.

### #terminado y BUG-005

El parser puede seguir produciendo:

logical termination protocol event

pero la frontera contractual queda fija:

parser result != physical release authorization

#terminado = logical protocol closure

#terminado != provider termination proof

El parser no se modifica en este gate. Su resultado solo puede disparar el flujo lógico que busca evidencia física posterior.

### Quarantine future contract

Propiedad mínima:

CANCELLED_WITHOUT_TERMINATION_EVIDENCE -> QUARANTINED

Y:

QUARANTINED + weak/arbitrary evidence -> QUARANTINED

No se permite:

QUARANTINED + arbitrary string -> AVAILABLE

La salida de quarantine debe usar evidencia tipada y correlacionada con el contexto de quarantine.

Separación obligatoria:

- TERMINATION prueba que la ejecución/proveedor alcanzó el estado terminal definido por su adapter;
- SANITIZATION prueba que el recurso quedó en condición segura de reutilización;
- RECONCILIATION observa/alinea estados y no debe convertir una cadena débil en autorización.

No se establece que todo reconcile() deba exigir un ACK de Gemini. La propiedad mínima es que una evidencia no tipada, no correlacionada o insuficiente no pueda limpiar quarantine.

### Cobertura conceptual de BUG-001 / BUG-003 / BUG-005

**BUG-001:** la evidencia string deja de ser una puerta de release. El release requiere evidencia TERMINATION tipada, contextualizada y correlacionada con la ejecución actual.

**BUG-003:** QUARANTINED solo puede salir mediante una transición cuyo propósito esté explícitamente definido y cuya evidencia sea tipada. SANITIZATION puede constituir la evidencia de reutilización segura cuando el contexto de quarantine sea válido; eso no significa que sanitation y termination sean equivalentes.

**BUG-005:** el parser sigue siendo un productor de evento lógico. Ningún match textual puede ser consumido directamente como provider termination proof.

Los tres convergen en una sola regla:

weak observation/protocol text
->
NO DIRECT RELEASE

trusted typed evidence + current identity
->
ADMISSION CANDIDATE

admission policy satisfied
->
AVAILABLE

### BUG-002

Se mantiene:

**P2 / CONSISTENCY FOLLOW-UP**

La observación de que la Authority puede estar AVAILABLE antes de que Reconciliation registre CONFIRMED permanece como ventana de consistencia.

El diseño mínimo no introduce 2PC.

La garantía adicional requerida, si una implementación futura la necesita, debe demostrar primero una consecuencia de seguridad; no se infiere 2PC de la mera divergencia temporal de metadata.

### BUG-004

Se mantiene:

**NOT DEMONSTRATED**

operation_id queda permitido como **defense-in-depth / conditional fencing key** cuando el evento lo requiera, pero no se implementa ni se eleva a bug confirmado en esta fase.

### Provider runtime y 2F-8T

Puede definirse sin runtime:

- typed evidence;
- trust boundary;
- identity binding;
- release admission;
- quarantine rules.

Queda bloqueado por 2F-8T:

- Gemini Web termination proof;
- provider terminal state;
- generación/correlación provider real;
- provider ACK o equivalente.

Estado de 2F-8T:

**VERIFIED BLOCKER / ROOT CAUSE UNKNOWN**

**NO REOPENED**

No se agrega ninguna conclusión nueva sobre Qt/QWebEngine.

### Secuencia mínima de implementación futura

No se implementa aquí.

1. Introducir la representación tipada de evidencia.
2. Hacer que la identidad de evidencia derive de la ejecución/claim actual y no del caller.
3. Endurecer release admission para aceptar solo evidencia typed TERMINATION suficiente.
4. Separar explícitamente TERMINATION y SANITIZATION.
5. Impedir weak evidence -> AVAILABLE, incluyendo #terminado.
6. Añadir regresiones de unidad/integración y fences de identidad.
7. Validar el provider runtime real una vez que 2F-8T deje de bloquear la evidencia física.

No se propone un refactor amplio ni una migración de backend en esta fase.

### Matriz de test futura

| Caso | Clasificación |
| --- | --- |
| arbitrary string -> REJECT | UNIT TEST |
| empty evidence -> REJECT | UNIT TEST |
| #terminado -> logical only | INTEGRATION TEST |
| typed TERMINATION + matching identity -> ACCEPT | UNIT + INTEGRATION |
| typed SANITIZATION + valid quarantine context -> ACCEPT | UNIT + INTEGRATION |
| stale generation -> REJECT | UNIT TEST |
| wrong claim -> REJECT | UNIT TEST |
| wrong resource -> REJECT | UNIT TEST |
| wrong operation when required -> REJECT | UNIT TEST |
| QUARANTINED + weak evidence -> remains QUARANTINED | INTEGRATION TEST |
| normal completion -> release only through trusted evidence | INTEGRATION TEST |
| provider terminal proof correlates to current execution | RUNTIME PROVIDER TEST |
| provider termination absence -> no AVAILABLE | RUNTIME PROVIDER TEST |
| provider sanitization proof -> quarantine exit only under valid context | RUNTIME PROVIDER TEST |

### Gate de diseño

**HUESO-09-MINIMAL-RELEASE-GATE-DESIGN**

**PROPOSED / NOT IMPLEMENTED**

La propuesta queda deliberadamente backend-neutral y no afirma que el provider runtime actual ya pueda producir la evidencia necesaria.

**No implementación. No root cause. No reapertura de 2F-8T.**

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
