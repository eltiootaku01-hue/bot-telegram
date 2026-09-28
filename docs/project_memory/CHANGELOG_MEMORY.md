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

- Estado: [PROPOSED]
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
- CI final: pendiente hasta que el HEAD de memoria esté construido.


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
- Repair attempts de implementación: 1.
- CI final: pendiente sobre el HEAD final de esta fase.
