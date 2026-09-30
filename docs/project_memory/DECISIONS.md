# Project Memory — Decisions

### DEC-008 — Task Contract separado del TaskEngine

- Estado: [DECIDED]
- Origen: FASE 2F-3.
- Decisión: implementar el contrato de tarea y su máquina de estados dentro de Supervisor sin sustituir TaskEngine.
- Motivo: preservar una sola autoridad operativa de ciclo de vida.
- Evidencia: implementación `src/bot_ia/supervisor/task_contract.py`; TaskEngine existente inspeccionado.
- Impacto: futuras integraciones requieren adapter explícito.
- No implica: integración física Supervisor → TaskEngine.
- Fuentes: FASE 2F-3.

### DEC-009 — Respuestas tardías por task_id

- Estado: [DECIDED] + [TESTED]
- Origen: FASE 2F-3.
- Decisión: una respuesta se valida exclusivamente contra task_id y el estado actual; UNKNOWN o terminal se descartan.
- Motivo: impedir que una respuesta tardía reactive o contamine otra tarea.
- Evidencia: tests de `TaskContractStore.validate_response`.
- Impacto: una tarea terminal no vuelve a ser RUNNING por una respuesta.
- No implica: transporte o ejecución física de respuestas.
- Fuentes: FASE 2F-3.

### DEC-010 — Scope Lock como referencia

- Estado: [DECIDED] + [TESTED]
- Origen: FASE 2F-3.
- Decisión: Task puede referenciar un ScopeLock existente mediante scope_id; no crea un sistema paralelo de permisos.
- Motivo: reutilización contractual.
- Evidencia: tests de scope reference.
- Impacto: scope_id requiere un ScopeLock válido en esta capa.
- No implica: enforcement físico.
- Fuentes: FASE 2F-3.

### DEC-011 — Authorization separada de Scope y Execution

- Estado: [DECIDED]
- Origen: FASE 2F-4.
- Decisión: WriteAuthorization es una capa contractual entre ScopeLock y cualquier ejecución futura; no ejecuta ni persiste escrituras.
- Motivo: separar permiso específico de alcance potencial y ejecución física.
- Evidencia: `src/bot_ia/supervisor/authorization.py` y tests de FASE 2F-4.
- Impacto: futuras escrituras deben presentar una autorización válida dentro de un ScopeLock válido.
- No implica: autoridad física definitiva ni integración runtime.
- Fuentes: FASE 2F-4.

### DEC-012 — Hypothesis y Repair como contratos no ejecutores

- Estado: [DECIDED]
- Origen: FASE 2F-5.
- Decisión: Hypothesis, RepairProposal, RepairAttempt, RepairBudget y VerificationResult forman una capa contractual sin escritura física.
- Motivo: preservar la separación OBSERVATION → EVIDENCE → CLAIM → HYPOTHESIS → REPAIR PROPOSAL → AUTHORIZATION → EXECUTION → VERIFICATION.
- Evidencia: src/bot_ia/supervisor/repair.py y tests de FASE 2F-5.
- Impacto: futuras reparaciones deben respetar hipótesis, propuesta, ScopeLock, autorización y presupuesto antes de cualquier ejecución.
- No implica: WriteExecutor, FileWriter, GitWriter, persistencia definitiva ni integración runtime.
- Fuentes: FASE 2F-5.

### DEC-013 — TaskEngine y TaskScheduler como autoridades operacionales únicas

- Estado: [DECIDED] + [TESTED]
- Origen: FASE 2F-6.
- Decisión: TaskEngine conserva la autoridad operacional sobre lifecycle; TaskScheduler conserva scheduling/routing/resource arbitration. Supervisor solo valida/observa mediante `TaskEngineBoundary`.
- Motivo: impedir un segundo TaskEngine o Scheduler y conservar una única fuente de verdad operacional.
- Evidencia: inspección de `src/bot_ia/core/task_engine.py`, `src/bot_ia/core/task_scheduler.py`, `src/bot_ia/supervisor/task_contract.py` y tests de `tests/test_supervisor_taskengine_boundary.py`.
- Impacto: el Task Contract de Supervisor queda como contrato superior/adaptador, no como segundo lifecycle.
- No implica: ejecución, dispatch, cancelación física ni integración automática.
- Fuentes: FASE 2F-6.


### DEC-014 — Runtime Observation es read-only

- Estado: [DECIDED] + [TESTED]
- Origen: FASE 2F-7.
- Decisión: `RuntimeObservation` utiliza exclusivamente snapshots de `TaskEngineBoundary` y registra evidencia mediante el modelo `Evidence` existente.
- Motivo: demostrar comportamiento real sin convertir Supervisor en TaskEngine, Scheduler o executor.
- Evidencia: `src/bot_ia/supervisor/runtime_observation.py` y `tests/test_supervisor_runtime_observation.py`.
- Impacto: lifecycle y scheduling continúan teniendo un único propietario operacional.
- No implica: ejecución física, dispatch desde Supervisor, WebQueue integration ni handoff automático.


### DEC-015 — WAITING/RESUME respeta ownership del Scheduler

- Estado: [TESTED]
- Origen: FASE 2F-7.
- Evidencia: el runtime real exige liberar el registro activo antes de `wake()`; la prueba se corrigió para representar la secuencia executor-finish → wake → dispatch.
- Decisión: la evidencia de WAITING/RESUME debe modelar el handoff existente y no inventar una transición Supervisor → wake.


### DEC-016 — Snapshot difference is not causal transition proof

- Estado: [DECIDED] + [TESTED]
- Origen: FASE 2F-8R F-001.
- Decisión: RuntimeObservation.transition() representa únicamente una diferencia observada entre snapshots. No eleva la evidencia a TESTED causal basándose en transition_source.
- Motivo: un string suministrado por el caller no demuestra que TaskEngine/TaskScheduler haya producido la transición.
- Evidencia: test adversarial de RuntimeObservation.
- Impacto: se evita sobreafirmar causalidad sin crear una segunda state machine.
- No implica: ejecución ni acceso directo de RuntimeObservation al Scheduler.

### DEC-017 — ScopeLock inmutable después de creación

- Estado: [DECIDED] + [TESTED]
- Origen: FASE 2F-8R F-002.
- Decisión: ScopeLock es frozen después de construcción; las normalizaciones internas se realizan durante __post_init__ mediante object.__setattr__.
- Motivo: impedir expansión o reducción silenciosa del alcance contractual después de su creación.
- Evidencia: test de mutación de paths, operations y status.
- Impacto: una modificación contractual requiere crear otro ScopeLock en lugar de alterar el existente.
- No implica: enforcement físico de ScopeLock.


### DEC-016 — Reconciliación F-006: alcance del TaskScheduler y GUI TaskOrchestrator

- Estado: [DECIDED / F-006 CONFLICT]
- `TaskScheduler` conserva ownership de scheduling/routing/resource arbitration dentro de su runtime `TaskEngine`; no es scheduler global del repositorio.
- `GUI TaskOrchestrator` mantiene un runtime asíncrono GUI separado, con su propia cola de prioridad, timeout, fallback y CircuitBreaker. No debe etiquetarse como legacy con la evidencia actual.
- Ambos caminos tienen responsabilidades WebChat operativas, pero utilizan identidades y componentes distintos: el TaskScheduler consume Tasks con `task_id`; TaskOrchestrator usa `waitress_id` + payload y no participa del Task Contract.
- La coexistencia operacional se clasifica como conflicto de ownership arquitectónico pendiente. Esta fase documenta el conflicto; no lo resuelve mediante refactorización.
- La formulación anterior de DEC-013 sobre autoridades "únicas" queda limitada al runtime TaskEngine/TaskScheduler y no debe interpretarse como unicidad global.


### DEC-017 — FASE 2F-8B: convergencia WebChat

- Estado: [DECIDED / PROPOSED IMPLEMENTATION]
- F-006 se resuelve arquitectónicamente mediante **CANDIDATO A**: el runtime operacional WebChat objetivo será `TaskEngine → TaskScheduler → WebChatQueueManager`.
- Motivo principal: es el único camino que integra identidad `task_id`, lifecycle TaskEngine, resource arbitration, dispatch, cancellation y el boundary observable por Supervisor.
- GUI TaskOrchestrator sigue siendo código operativo actual, pero no se considera el owner definitivo del WebChat operacional.
- CANDIDATO B se descarta como arquitectura objetivo porque no existen fronteras de recurso suficientes entre ambos caminos: `WEB_MESA_UNICA` pertenece al WebChatQueueManager del runtime TaskScheduler y no coordina la cola Playwright del TaskOrchestrator.
- CANDIDATO C no describe el estado actual: TaskOrchestrator sí posee scheduling propio (PriorityQueue, prioridades, timeout y CircuitBreaker). Sólo podría convertirse en capa GUI mediante una migración futura.
- CANDIDATO D no está sustentado: TaskOrchestrator tiene instanciación y uso operativo actual.
- No se modifica ningún runtime protegido en esta fase.
- La convergencia, adapter futuro, migración de quick actions y retirada eventual del TaskOrchestrator son PROPOSED y requieren una fase de implementación separada.


### DEC-018 — FASE 2F-8C: Migration Contract WebChat

- Estado: [DECIDED / PROPOSED IMPLEMENTATION]
- F-006 mantiene como arquitectura objetivo CANDIDATE A: `GUI → TaskEngine → TaskScheduler → WebChatTaskExecutor → WebChatQueueManager`.
- [DECIDED] `task_id` es la única identidad operacional de una ejecución. No se sustituye por `waitress_id`, `ticket_id` ni `operation_id`; los últimos son identificadores de otras capas.
- [PROPOSED] Quick actions WebChat deberán crear TaskEngine Tasks con `task_id` generado por TaskEngine, prioridad, deadline/timeout policy, metadata y payload/contexto; después deberán registrarse en TaskScheduler con `WEB_MESA_UNICA`.
- [PROPOSED] El callback de TaskOrchestrator no debe migrarse como lifecycle paralelo. El resultado futuro debe pasar por la finalización/validación del TaskEngine y sólo después llegar a la GUI como notificación de presentación.
- [PROPOSED] El owner futuro de scheduling será TaskScheduler; el owner futuro de lifecycle será TaskEngine; el owner futuro de WebChat físico será WebChatTaskExecutor → WebChatQueueManager; GUI sólo presentará/solicitará.
- [PROPOSED] `WEB_MESA_UNICA` será el recurso común de las quick actions WebChat. No se crea un segundo lock para el mismo recurso.
- [PROPOSED] La migración temporal debe usar un routing switch/adapter que seleccione exactamente una ruta por solicitud. No se permite shadow execution ni doble dispatch.
- [PROPOSED] El fallback debe ser clasificado por responsabilidad: resultado alternativo de presentación puede continuar siendo GUI, pero un retry WebChat debe conservar la identidad operacional o crear explícitamente un child task mediante TaskEngine; nunca una ejecución huérfana.
- [PROPOSED] CircuitBreaker futuro: la política de disponibilidad WebChat debe tener un owner operacional único. El CircuitBreaker del executor físico puede sobrevivir si protege exclusivamente WebChatQueueManager; el CircuitBreaker por waitress del TaskOrchestrator no debe duplicarse sin una semántica distinta demostrable.
- [PROPOSED] Cancellation debe seguir `TaskEngine → TaskScheduler → WebChatTaskExecutor → WebChatQueueManager`; TaskEngine confirma lifecycle y el executor sólo cancela el trabajo físico asociado al mismo `task_id`.
- [UNKNOWN] La equivalencia exacta de prioridades ya coincide en representación (`TaskOrchestrator`: HIGH=1/MEDIUM=2/LOW=3; TaskEngine: HIGH=1/MEDIUM=2/LOW=3), pero la semántica final de fairness/starvation debe seguir siendo responsabilidad de TaskScheduler.
- [PROPOSED] Los timeouts deben separarse en deadline/lifecycle (TaskEngine), espera de scheduling/recurso (TaskScheduler, sin nuevo timeout salvo necesidad demostrada) y ejecución física WebChat (WebChatQueueManager). El timeout de 12 s del Orchestrator no se traslada automáticamente.
- [UNKNOWN] La traducción exacta de RESPONSE_TIMEOUT_MS/PAGE_TIMEOUT_MS/NAVIGATION_TIMEOUT_MS del Playwright a QWebEngine todavía requiere pruebas funcionales.
- [PROPOSED] La identidad de sesión no se fusiona con task_id: session_id sigue siendo owner de WaitressSessionManager y ticket_id puede continuar como alias histórico sólo donde el runtime ya lo exige; la convergencia futura debe evitar crear otro task_id.
- [PROPOSED] Authorization y ScopeLock deberán vincularse al mismo task_id antes de cualquier enforcement físico futuro; esta fase no implementa enforcement.
- [PROPOSED] RuntimeObservation seguirá siendo read-only y observará el TaskEngine/Scheduler convergido, no al executor directamente.


### DEC-019 — FASE 2F-8D: MIG-0 Capability Verification & Migration Gates

- Estado: [DECIDED / MIG-0 PARTIAL]
- MIG-0 sólo define gates, evidencia y requisitos de verificación; no aprueba MIG-3 ni ninguna migración física.
- [DECIDED] Ninguna afirmación de paridad Playwright/QWebEngine se considera cerrada por inspección estática.
- [DECIDED] task_id continúa siendo la identidad de lifecycle; waitress_id, session_id, ticket_id y operation_id conservan sus scopes separados.
- [DECIDED] No se copian cookies, storage_state, perfiles ni credenciales para cerrar UNKNOWNs.
- [DECIDED] Quick actions WebChat futuras deberán entrar por TaskEngine/TaskScheduler y WEB_MESA_UNICA.
- [CONFIRMED RISK] El callback actual de quick action depende de _selected_bot_id mutable al momento de completion.
- [DECIDED] Este riesgo se documenta pero no se repara en MIG-0.
- [DECIDED] MIG-1..MIG-6 permanecen sin iniciar.

### DEC-0XX — MIG-3 evidence is mechanism-level, not migration parity

- Estado: [DECIDED]
- Origen: FASE 2F-8E.
- Decisión: TESTED/OBSERVED gates in MIG-3 describe deterministic evidence of existing mechanisms; they do not certify Playwright ↔ QWebEngine parity or authorize migration.
- Motivo: preserve evidence-before-conclusion and avoid promoting static structure into runtime equivalence.
- Impacto: G01-G04, G07-G11 and G15 remain UNKNOWN where real browser/provider/session evidence is required.
- No implica: MIG-1 authorization or physical routing changes.

### DEC-0XY — Scheduler remains the sole resource arbiter in the target path

- Estado: [DECIDED]
- Origen: FASE 2F-8E.
- Decisión: WEB_MESA_UNICA evidence is accepted only for the existing TaskScheduler/WebChatQueueManager path; the Playwright WebQueueManager remains outside that resource lock.
- Motivo: current tests prove separate mechanisms, not a global cross-runtime lock.
- Impacto: G20 remains OBSERVED and is a migration blocker for quick-action convergence.

### DEC-020 — checkpoint histórico main@78d5

- [DECIDED] En ese checkpoint histórico, la rama canónica era `main@78d5fa6d0b539991aba1ee700121404678c21e59`.
- [DECIDED] La línea funcional válida es `2902...` → `9fe...` → `78d5...`.
- [CURRENT] El HEAD actual de `main` es `1763974f4dc27fb5ea5f66452c0f9b57297aaa76`, descendiente directo de `78d5...`; `78d5...` permanece como LAST FUNCTIONAL BASELINE.
- [DECIDED] `603266...` permanece archivado como artefacto lateral y no se integra automáticamente.
- [DECIDED] `b6265...` se conserva como validación histórica D3; no es ancestro de `main`.

### DEC-021 — Lifecycle lógico y físico son autoridades distintas

- [DECIDED] `TaskEngine` es owner del lifecycle lógico y nunca decide por sí solo `AVAILABLE` físico.
- [DECIDED] `PhysicalWebChatResourceAuthority` es la única fuente de verdad del ownership/estado físico dentro de un runtime.
- [DECIDED] `PhysicalLifecycleReconciliation` es puente y metadata, no segunda autoridad.
- [DECIDED] `COMPLETED`, `CANCELLED` y `TIMED_OUT` no implican automáticamente recurso físico `AVAILABLE`.

### DEC-022 — D3 preserva el orden de S03

- [DECIDED] `RUNNING + BUSY → TaskEngine.complete() → COMPLETED + BUSY → record_termination() → COMPLETED + AVAILABLE → ALIGNED`.
- [DECIDED] La terminación física requiere evidencia separada y binding/generation actuales.
