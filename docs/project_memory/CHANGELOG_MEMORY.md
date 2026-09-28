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

