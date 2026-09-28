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
