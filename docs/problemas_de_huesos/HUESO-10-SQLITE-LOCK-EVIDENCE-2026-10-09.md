# HUESO-10 — SQLITE LOCK EVIDENCE REPORT

Date: 2026-10-09

## 1. PURPOSE

Persist the previously reported diagnostic evidence for HUESO-10 and synchronize its architectural status. This is a documentation-only record. No SQLite validation was executed again during this gate.

## 2. BASELINE

- Repository: `eltiootaku01-hue/bot-telegram`
- Verified main baseline: `9b191e578e86a65522cc374bdda24e53d386df37`
- Baseline commit: [`9b191e5`](https://github.com/eltiootaku01-hue/bot-telegram/commit/9b191e578e86a65522cc374bdda24e53d386df37)
- HUESO-05 remains documented as `CLOSED / VERIFIED REPAIR + PASS`; this report does not alter it.
- Source of truth: GitHub.

## 3. EXPERIMENT ENVIRONMENT

**REPORTED — PRIOR EXECUTION**

The previous diagnostic reports describe a temporary external harness using real SQLite, two independent OS processes, independent connections, and a temporary database.

Reported environment:

- Python 3.13.5
- SQLAlchemy 2.0.50
- SQLite 3.46.1

CI reportedly configures Python 3.14. This report does not claim parity between those environments.

## 4. REPRODUCED SQLITE LOCK

**REPORTED — PRIOR EXECUTION**

The previous experiments reported:

```text
REAL SQLITE
TEMPORARY DATABASE
TWO INDEPENDENT PROCESSES
INDEPENDENT CONNECTIONS
BEGIN IMMEDIATE
sqlite3.OperationalError: database is locked
```

Reported repetitions:
- Three reproductions with an approximately five-second timeout.
- Three additional reproductions with a 300 ms test timeout.
- `PRAGMA integrity_check = ok` in the described concurrent-write scenarios.

**VERIFIED — REPORTED CONTROLLED EXPERIMENT:** a lock was reproduced in the isolated harness according to the prior execution reports.

**NOT DEMONSTRATED:** the same sequence occurred in a production incident.

## 5. WRITER / WRITER RESULTS

**REPORTED — PRIOR EXECUTION**

Writer-versus-writer contention failed with `database is locked` under both journal modes tested:

- `DELETE`
- `WAL`

The result demonstrates that WAL did not eliminate writer/writer contention in the tested scenario. It does not establish a production defect or a universal behavior for every transaction path.

## 6. DELETE VS WAL OBSERVATIONS

**REPORTED — PRIOR EXECUTION**

The previous experiments reported a behavioral difference between `DELETE` and `WAL` in a scenario where a reader was held while a writer attempted to commit.

The exact timings, operation trace, and service-level correspondence were not provided as reproducible repository artifacts in the evidence available to this documentation gate. No stronger claim is made here.

WAL is not treated as a guarantee of lock-free operation.

## 7. CONTRIBUTING FACTORS

**VERIFIED IN THE CONTROLLED EXPERIMENT — REPORTED BY PRIOR EXECUTIONS**

- Two independent processes and connections attempted concurrent write work.
- A transaction used `BEGIN IMMEDIATE`, which reserves write access before later work in that transaction.
- Writer/writer contention was associated with the observed lock exception in the controlled harness.

These are contributing conditions observed/reported within the experiment, not a proven root cause for a production incident.

**NOT ISOLATED / NOT DEMONSTRATED**

- The exact original-service transaction path.
- A specific production Engine or pool as the cause.
- A particular production timeout or journal mode as the cause.
- Whether a production incident followed the same lock schedule.
- Whether the behavior is identical under CI's reported Python 3.14 environment.

## 8. PRODUCTION-PATH LIMITATIONS

**NOT DEMONSTRATED**

The level-3 validation did not execute the original service functions. The experiment used a temporary harness external to the repository. Therefore, it cannot establish that the original application has the same transaction sequence or that a real production incident has been reproduced.

No production database was tested or modified by this documentation gate.

## 9. LEVEL-3 VALIDATION BLOCKER

**BLOCKED — NOT EXECUTED**

The last reported re-entry attempts ended with:

```text
EXECUTION BLOCKED — REQUIRED CHECKOUT NOT ACCESSIBLE
```

The service-level validation remains blocked. This gate does not retry checkout access and does not substitute another generic harness.

## 10. ROOT CAUSE STATUS

- SQLite lock in isolated harness: **REPRODUCED — REPORTED BY PRIOR EXECUTIONS**
- Contributing factor in controlled experiment: **VERIFIED — REPORTED BY PRIOR EXECUTIONS**
- Production incident: **NOT DEMONSTRATED**
- Exact service transaction path: **NOT VERIFIED**
- Production root cause: **UNKNOWN**
- HUESO-10: **OPEN / HIGH**
- Implementation: **NOT AUTHORIZED**

No root cause is declared.

## 11. REQUIRED NEXT EVIDENCE

The next technical gate is level-3 validation using the original service functions, when the corresponding checkout is verifiably accessible. It must use a temporary isolated database and record the actual transaction path, independent processes/connections, operation sequence, journal mode, timeout behavior, exception, and final database state.

The gate must separate:
1. service-path reproduction;
2. any actual production incident;
3. causal isolation.

A separate implementation gate is required after adjudication. No repair is authorized by this report.

## 12. GOVERNANCE

- This report records prior reported executions; it does not claim they were rerun here.
- Scope is documentation only.
- No source code, tests, workflow, database, schema, timeout, WAL setting, or transaction logic was changed.
- HUESO-05 remains closed as recorded in the existing architecture registry.
- HUESO-10 remains open at HIGH priority.
- 2F-8T remains frozen and untouched.
- No PR is merged by this gate.
