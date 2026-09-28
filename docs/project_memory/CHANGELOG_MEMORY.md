# Project Memory — Changelog

## FASE 2F-3

- Estado: [TESTED]
- Branch: `feature/supervisor-task-contract`.
- HEAD base: `2c94915ea51b39c5e514b809cab332a630cefbf0`.
- Alcance: Task Contract + State Machine contractual.
- Producción: `src/bot_ia/supervisor/task_contract.py`, actualización de `__init__.py`.
- Tests: `tests/test_supervisor_task_contract.py`.
- TaskEngine modificado: NO.
- TaskScheduler modificado: NO.
- WebQueue modificado: NO.
- DB: NO.
- Workflows: NO.
- Dependencias: NO.
- Integración física: NO.
- Repair attempts: 0.
- Fecha: [UNKNOWN].

## FASE 2F-4

- Estado: [TESTED]
- Branch: `feature/supervisor-write-authorization`.
- HEAD base: `74836bed7f27aed6d3635db5574160cb93a4c026`.
- CI base: workflow `36437000704`, conclusión `success`.
- Alcance: Write Authorization contractual, default deny, independent authority validation, task/scope/operation/target binding, expiration, revocation e immutability.
- Producción creada: `src/bot_ia/supervisor/authorization.py`.
- Producción modificada: `src/bot_ia/supervisor/__init__.py`.
- Tests creados: `tests/test_supervisor_authorization.py`.
- TaskEngine modificado: NO.
- TaskScheduler modificado: NO.
- WebQueue modificado: NO.
- Telegram/Discord/TCG/TMA/GUI modificados: NO.
- DB: NO.
- Workflows: NO.
- Dependencias: NO.
- Persistencia de Authorization: NO.
- WriteExecutor: NO.
- Repair attempts: 0.
- Fecha: [UNKNOWN].


## FASE 2F-5

- Estado: [TESTED]
- Branch: feature/supervisor-repair-hypothesis.
- HEAD base: 958c7eb84d0e5831547a347099edb88c88c46231.
- Alcance: Hypothesis, RepairProposal, RepairAttempt, RepairBudget y VerificationResult contractuales.
- Producción creada: src/bot_ia/supervisor/repair.py.
- Tests creados: tests/test_supervisor_repair.py.
- Ejecución física: NO.
- Persistencia nueva: NO.
- AuthorityCore/TaskEngine/TaskScheduler/WebQueue/Telegram/Discord/TCG/TMA/GUI/DB/workflows/dependencias: NO modificados.
- Repair attempts de implementación: 3; los dos primeros ciclos CI detectaron fallos de tests y el tercer ciclo terminó con CI verde.
- Fecha: [UNKNOWN].

## FASE 2F-6

- Estado: [TESTED]
- Branch: `feature/supervisor-taskengine-boundary`.
- HEAD base: `0e3d04ee8d15e58ffeb7e635f526cbe5e1aa36e5`.
- Alcance: frontera contractual/read-only entre Supervisor, TaskEngine y TaskScheduler.
- Producción creada: `src/bot_ia/supervisor/boundary.py`.
- Tests creados: `tests/test_supervisor_taskengine_boundary.py`.
- TaskEngine modificado: NO.
- TaskScheduler modificado: NO.
- WebQueue modificado: NO.
- AuthorityCore modificado: NO.
- Telegram/Discord/TCG/TMA/GUI modificado: NO.
- DB: NO.
- Workflows: NO.
- Dependencias: NO.
- Ejecución física: NO.
- Runtime observation residente: NO.
- Commits de implementación antes de memoria: 2.
- Repair attempts de implementación: 0.
- CI final: workflow `36454348810`, Ubuntu/Windows success.


## FASE 2F-7

- Estado: [TESTED]
- Branch: `feature/supervisor-runtime-observation`.
- HEAD base: `490721c22761bdccf088da91efe0c82786532b3a`.
- Alcance: observación read-only del TaskEngine y TaskScheduler reales mediante el boundary existente.
- Producción creada: `src/bot_ia/supervisor/runtime_observation.py`.
- Producción modificada: `src/bot_ia/supervisor/boundary.py` para incluir timestamps/deadline en snapshots read-only.
- Tests creados: `tests/test_supervisor_runtime_observation.py`.
- TaskEngine modificado: NO.
- TaskScheduler modificado: NO.
- WebQueue/AuthorityCore/Telegram/Discord/TCG/TMA/GUI/DB/workflows/dependencias: NO.
- Ejecución física desde Supervisor: NO.
- Persistencia nueva: NO.
- Runtime observation residente: NO.
- Repair attempts de implementación: 2.
- CI final: workflow `36488124932`, Ubuntu/Windows success.


### Corrección final FASE 2F-7

- [TESTED] Primer CI del HEAD de implementación: 700 passed / 8 failed por referencia interna inexistente del observador.
- [TESTED] Repair 1 eliminó la referencia interna y dejó 707 passed / 1 failed: el fallo reveló que `TaskScheduler.wake()` requiere que la tarea WAITING no esté activa.
- [TESTED] Repair 2 corrigió únicamente el escenario de prueba para modelar `execution_finished → wake`.
- [TESTED] CI del HEAD `5fea2df4a54eddeb8ff0949b5258767bce297712`: Ubuntu y Windows success.
- [TESTED] Repair attempts consumidos: 2 de 3.


## FASE 2F-8R — Repair & Re-verification

- Estado: [TESTED]
- Branch: `feature/supervisor-runtime-observation`.
- HEAD base: `7cabafdc4f8ee3d8737074d783951ae6daa204af`.
- Alcance: reparación controlada de F-001 y F-002 sin ejecución física.
- Repair 1 / F-001: RuntimeObservation.transition() dejó de etiquetar diferencias de snapshots como TESTED causal; ahora registra OBSERVED y causal_transition_verified=false.
- Repair 2 / F-002: ScopeLock pasó a frozen y se añadió prueba de inmutabilidad.
- No se modificaron TaskEngine, TaskScheduler, WebQueue ni AuthorityCore.
- No se creó executor, scheduler, store ni sistema de autorización adicional.
- CI de re-verificación: workflow `36491889698`, Ubuntu/Windows success, 710 passed.


## FASE 2F-8A — F-006 Ownership reconciliation

- Alcance: auditoría y documentación de ownership; sin ejecución física.
- [TESTED] Se añadieron pruebas read-only para separar TaskScheduler/TaskEngine de GUI TaskOrchestrator y comprobar ausencia de acceso directo del Supervisor a GUI TaskOrchestrator/WebQueue.
- [DECIDED] TaskScheduler se describe como scheduler del runtime TaskEngine, no como scheduler global.
- [CONFLICT] GUI TaskOrchestrator permanece activo y separado; no se clasifica como legacy.
- [CONFLICT] Ambos caminos tienen trabajo WebChat operativo con colas/control distintos; la decisión de convergencia queda pendiente.
- TaskEngine/TaskScheduler/WebQueue/AuthorityCore: NO modificados.
- Ejecución física del Supervisor: NO implementada.
- FASE 2F-8R repair budget: permanece históricamente en 2/3; esta fase usa su propio presupuesto y no consume ese intento.
