# -*- coding: utf-8 -*-
# WORLD-01-B — Café Otaku Persistence Contract
## Persistence Contract Review — 2026-10-01

> **Scope:** architecture, database discovery and persistence contract only.
>
> **Runtime implementation:** explicitly out of scope.
>
> **Base reviewed:** `world-01-a-lobby-design @ 2832965ac53aab0e6c1c099d7595217d171e7cea`

---

## 1. Purpose

WORLD-01-B verifies whether the inherited Social World persistence host remains technically suitable and converts the WORLD-01-A persistence intent into an implementation-ready contract for:

- `CafeSession`;
- `CafeParticipant`.

This document does **not** create tables, models, repositories, services, migrations, APIs or TMA code.

### Evidence vocabulary

- **OBSERVED** — directly found in repository/tool evidence.
- **VERIFIED** — independently checked against repository evidence and/or authoritative technical documentation.
- **INFERENCE** — conclusion derived from observed evidence.
- **HYPOTHESIS** — not established sufficiently for implementation.
- **UNKNOWN** — evidence is not available.
- **BLOCKED** — an incompatibility or missing prerequisite prevents the phase from closing.

---

## 2. Existing persistence architecture

### 2.1 Repository state inspected

**OBSERVED**

The reviewed commit contains:

- `src/bot_ia/persistence/economy.py`;
- `src/bot_ia/interfaces/telegram_event_ledger.py`;
- `src/bot_ia/interfaces/telegram_outbox.py`;
- `src/bot_ia/interfaces/telegram_room_routing.py`;
- `src/bot_ia/memory/store.py`;
- `src/bot_ia/memory/schema.sql`;
- `src/bot_ia/core/session_store.py`;
- `src/bot_ia/core/sqlite_backup.py`;
- `src/bot_ia/core/backup_service.py`;
- root `alembic.ini`;
- `alembic/env.py`;
- `alembic/versions/*`;
- root `pyproject.toml`.

The repository does **not** contain a versioned binary file named:

`config/bot_ia_events.sqlite3`.

Therefore the requested host is a **runtime database**, not repository source.

### 2.2 Existing SQLite connection pattern

**OBSERVED**

The Telegram Event Ledger opens SQLite with:

- `timeout=15.0`;
- `isolation_level=None`;
- `check_same_thread=False`;
- `PRAGMA busy_timeout=15000`;
- `PRAGMA foreign_keys=ON`;
- `PRAGMA journal_mode=WAL`;
- explicit `BEGIN IMMEDIATE`;
- explicit `COMMIT`;
- explicit rollback on failure;
- connection close after each operation.

The Telegram Outbox uses a 15-second timeout, `busy_timeout=15000`, foreign keys ON and WAL.

The Telegram Room Router uses a 15-second timeout, `busy_timeout=15000`, WAL and `synchronous=NORMAL`, and closes each connection after use.

### 2.3 Existing Telegram tables

**OBSERVED**

`TelegramEventLedger` owns:

`telegram_events`

with:

- `event_type`;
- `event_id`;
- `update_id`;
- `status`;
- `metadata`;
- `created_at`;
- `updated_at`;
- primary key `(event_type, event_id)`;
- index on `update_id`.

`TelegramOutboxStore` owns:

- `telegram_outbox`;
- `telegram_outbox_followups`.

The followups table has a foreign key to `telegram_outbox(update_id)` with `ON DELETE CASCADE`.

`TelegramRoomRouter` owns:

`telegram_room_routes`

with primary key:

`(chat_id, message_thread_id)`

and an index on:

`(chat_id, room_key)`.

The router resolves:

`(chat_id, message_thread_id) → room_key`

and refuses to silently map an unknown topic to GENERAL.

### 2.4 Global SQLite header metadata

**OBSERVED**

`TelegramEventLedger` currently uses:

- `PRAGMA application_id` with application ID `0x54474556`;
- `PRAGMA user_version` with schema version `1`.

It rejects a database whose application ID belongs to another application and rejects a database whose `user_version` is newer than the supported value.

**VERIFIED**

SQLite documents `application_id` and `user_version` as database-header fields. `user_version` is an application-controlled integer and is not interpreted by SQLite itself.

**INFERENCE**

Social World must **not** independently claim the database-wide `application_id` or `user_version`. Doing so would conflict with the already existing Telegram Event Ledger contract.

This is a critical migration constraint.

---

## 3. Verified host compatibility

### 3.1 Host decision

**VERIFIED**

The inherited host remains:

`config/bot_ia_events.sqlite3`

No second SQLite file is selected.

### 3.2 Why the host is structurally compatible

**VERIFIED**

The repository already demonstrates that the intended host family supports:

- multiple independent tables owned by different subsystems;
- WAL;
- multiple short-lived connections;
- explicit transactions;
- 15-second busy timeouts;
- foreign-key enforcement per connection;
- concurrent read access;
- serialized write transactions.

SQLite's official documentation states that WAL permits readers and a writer to operate concurrently, while SQLite still serializes writers. WAL also requires all participating processes to use the same host/filesystem; it is not suitable for a network filesystem.

The project already uses WAL in the relevant SQLite stores.

### 3.3 Important compatibility boundary

**VERIFIED**

The host is compatible with the Social World tables **without changing the Telegram-owned tables**.

The following are explicitly prohibited:

- changing `telegram_events`;
- changing `telegram_outbox`;
- changing `telegram_outbox_followups`;
- changing `telegram_room_routes`;
- copying Telegram rows into Social World tables as a second source of truth;
- changing the existing database-wide application ID;
- taking ownership of the existing database-wide user-version field.

### 3.4 Actual runtime database state

**UNKNOWN**

The repository does not contain the physical `config/bot_ia_events.sqlite3` file, so this phase cannot directly inspect its live:

- `PRAGMA journal_mode`;
- `PRAGMA foreign_keys`;
- `PRAGMA application_id`;
- `PRAGMA user_version`;
- `PRAGMA integrity_check`;
- current schema;
- WAL sidecar state;
- filesystem/backup state.

Compatibility is therefore verified from the repository's persistence implementation and SQLite documentation, not from a physical production database instance.

### 3.5 Compatibility result

**COMPATIBLE**

The host is structurally compatible with `CafeSession` and `CafeParticipant`.

This result does **not** claim that the physical runtime database has been inspected. The implementation handoff must validate the actual database before applying migrations.

---

## 4. Database ownership

### 4.1 Host versus ownership

**VERIFIED**

`config/bot_ia_events.sqlite3` is a **host**.

Ownership is per table:

- Telegram infrastructure owns its Telegram tables.
- Social World owns its Social World tables.
- Neither subsystem owns the other's tables.

### 4.2 Social World ownership

WORLD-01 owns only:

- `CafeSession`;
- `CafeParticipant`.

No persistent `CafeRoom`, `CafeTable`, `CafeWallet` or `CafeActivityOwner` table is part of this contract.

### 4.3 Existing unrelated persistence

**OBSERVED**

The repository also contains separate persistence surfaces such as:

- `bot_database.db` through SQLAlchemy/Alembic;
- `bot_ia_economy.sqlite3`;
- `bot_ia_memory.sqlite3`;
- `bot_ia_sessions.sqlite3`;
- the Telegram event/outbox/room-routing host.

WORLD-01 does not move existing data between those stores.

---

## 5. CafeRoom reference contract

### 5.1 No CafeRoom table

**VERIFIED**

`CafeRoom` remains a domain/read projection.

No `cafe_rooms` table is created by WORLD-01.

### 5.2 Authoritative Room identity

**OBSERVED**

The actual Telegram router uses:

`(chat_id, message_thread_id) → room_key`

with `(chat_id, message_thread_id)` as the primary key of `telegram_room_routes`.

### 5.3 room_ref decision

**VERIFIED**

A persisted `room_ref` containing only `room_key` is **not sufficient as the authoritative identity contract**, because the current router schema does not establish `room_key` as a globally unique key.

Therefore:

> `CafeSession.room_ref` is a server-derived canonical logical reference to the resolved Telegram Room identity, derived from the complete router identity `(chat_id, message_thread_id)` and its resolved `room_key`.

The persisted value is:

- generated server-side;
- never accepted from the TMA as authority;
- stable for the session's lifetime;
- sufficient to distinguish Rooms across chats/topics;
- not a foreign key to `telegram_room_routes`.

The exact string serialization of the logical reference is an implementation detail; the semantic identity is not.

### 5.4 Snapshot semantics

The session keeps the resolved Room reference needed to identify the Room for which the session was created.

It does not duplicate the Telegram routing table.

If routing changes later, the session's historical `room_ref` remains the identity recorded for that session. Authorization for a new request must still resolve the current Room through the authoritative Telegram routing/context path.

---

## 6. CafeSession schema contract

### 6.1 Exact conceptual schema

| Field | Type | Null | Contract |
|---|---|---:|---|
| `session_id` | TEXT | NO | UUID-form internal identifier |
| `room_ref` | TEXT | NO | Server-derived canonical Room reference |
| `status` | TEXT | NO | ACTIVE / EXPIRED / CLOSED |
| `created_at` | TEXT | NO | UTC, timezone-aware ISO-8601 |
| `last_activity_at` | TEXT | NO | UTC, timezone-aware ISO-8601 |
| `expires_at` | TEXT | NO | UTC, timezone-aware ISO-8601 |
| `closed_at` | TEXT | YES | UTC, timezone-aware ISO-8601; required only for CLOSED |
| `version` | INTEGER | NO | Starts at 1; increments on state mutation |

### 6.2 session_id decision

**OBSERVED**

The repository already uses TEXT UUID-form identifiers for logical records, including:

- `CardInstance.id`;
- `ActiveMatch.id`;
- memory records generated with `uuid4()`.

**VERIFIED**

Use `TEXT` containing a UUID-form identifier for `CafeSession.session_id`.

This matches existing logical-ID conventions, avoids dependence on SQLite row IDs, and is suitable for serialization/API exposure later.

No integer AUTOINCREMENT identifier is introduced.

### 6.3 Status state machine

**VERIFIED**

Allowed values are exactly:

- `ACTIVE`;
- `EXPIRED`;
- `CLOSED`.

Legal transitions:

```
ACTIVE → EXPIRED
ACTIVE → CLOSED
```

Illegal transitions include:

- EXPIRED → ACTIVE;
- CLOSED → ACTIVE;
- EXPIRED → CLOSED;
- CLOSED → EXPIRED.

Expiry is a lifecycle result, not a new session status.

`CLOSED` is an explicit close operation.

### 6.4 Timestamp convention

**OBSERVED**

The repository's hardened memory/session code uses `datetime.now(timezone.utc)` and ISO serialization, and explicitly rejects naive persisted session timestamps.

**VERIFIED**

Social World uses one timestamp convention:

- UTC;
- timezone-aware;
- ISO-8601 text;
- comparisons performed using the same UTC representation.

No local-time timestamps are stored.

### 6.5 closed_at invariant

- `ACTIVE` → `closed_at IS NULL`.
- `EXPIRED` → `closed_at IS NULL`.
- `CLOSED` → `closed_at IS NOT NULL`.

Expiry does not masquerade as a manual close.

---

## 7. CafeParticipant schema contract

### 7.1 Exact conceptual schema

| Field | Type | Null | Contract |
|---|---|---:|---|
| `participant_id` | TEXT | NO | UUID-form membership-record identifier |
| `session_id` | TEXT | NO | FK to `CafeSession.session_id` |
| `actor_key` | TEXT | NO | Validated server-derived ActorKey |
| `membership_state` | TEXT | NO | ACTIVE / LEFT / EXPIRED |
| `joined_at` | TEXT | NO | UTC, timezone-aware ISO-8601 |
| `last_seen_at` | TEXT | NO | UTC, timezone-aware ISO-8601 |
| `left_at` | TEXT | YES | UTC, timezone-aware ISO-8601 |
| `version` | INTEGER | NO | Starts at 1; increments on mutation |

### 7.2 role field decision

**VERIFIED**

The WORLD-01-A document proposed `role` as USER / future MODERATOR.

No concrete WORLD-01 authorization role beyond participant membership is currently established by the inspected persistence/router architecture.

Therefore `role` is **not persisted in W01**.

Reason:

- avoids speculative authorization state;
- does not pre-allocate a future moderation model;
- membership authorization remains external to this persistence contract;
- a future moderator role can be introduced through a later reviewed migration.

This is a W01-B schema refinement, not a change to the Room architecture.

### 7.3 ActorKey

**VERIFIED**

The Social World contract remains:

`<platform>:<platform_user_id>`

Examples:

- `telegram:123`;
- `discord:123`.

These are distinct identities.

`actor_key` is not a foreign key to `src/db/models.py::User`.

The TCG User model is not the Social World Actor authority.

### 7.4 Membership states

Allowed values are exactly:

- `ACTIVE`;
- `LEFT`;
- `EXPIRED`.

Legal transitions:

```
ACTIVE → LEFT
ACTIVE → EXPIRED
```

No automatic transition from LEFT back to ACTIVE occurs on join.

---

## 8. Constraint contract

### 8.1 One active CafeSession per Room

**VERIFIED**

Use a SQLite partial unique index:

```
UNIQUE(room_ref) WHERE status = 'ACTIVE'
```

This is the database-enforced invariant.

A pre-check such as:

```
SELECT ...
if none:
    INSERT ...
```

is insufficient by itself because two concurrent writers can both observe no active row.

The unique partial index is authoritative.

### 8.2 One active participant per Actor/session

**VERIFIED**

Use:

```
UNIQUE(session_id, actor_key)
WHERE membership_state = 'ACTIVE'
```

This permits historical LEFT/EXPIRED rows while preventing duplicate ACTIVE memberships.

### 8.3 Participant rejoin semantics

**VERIFIED**

- ACTIVE + join again → reuse the existing ACTIVE row and update `last_seen_at`.
- LEFT + join → create a **new** participant membership row.
- EXPIRED + join → does not reactivate the old row; a new session/member is created if the Room is otherwise eligible.
- session EXPIRED/CLOSED → no new participant is attached to that session.

Creating a new row after LEFT preserves the history of the previous membership.

### 8.4 Foreign key

**VERIFIED**

`CafeParticipant.session_id` references `CafeSession.session_id`.

The relationship is enforced with:

```
ON DELETE RESTRICT
```

No DELETE CASCADE is used.

The normal Social World lifecycle does not physically delete sessions.

### 8.5 Foreign-key enforcement strategy

**VERIFIED**

SQLite foreign-key enforcement is per connection and is not safe to assume from the database file alone.

Every Social World connection must therefore:

1. open the database;
2. execute `PRAGMA foreign_keys=ON`;
3. verify that it is enabled before persistence operations;
4. only then perform transactions.

The existing Telegram persistence code already follows this pattern in the Event Ledger and Outbox.

---

## 9. Index contract

Only non-redundant critical indexes are required.

### CafeSession

1. Partial unique index:
   `room_ref WHERE status='ACTIVE'`

   Supports:
   - find active session for Room;
   - enforce one active session.

2. Partial index:
   `expires_at WHERE status='ACTIVE'`

   Supports:
   - find sessions eligible for expiry evaluation.

No additional `room_ref,status` index is required because the active-session unique index directly covers the critical active lookup.

### CafeParticipant

1. Partial unique index:
   `session_id, actor_key WHERE membership_state='ACTIVE'`

   Supports:
   - active membership lookup;
   - duplicate-join protection.

2. Index:
   `session_id, membership_state`

   Supports:
   - list active participants;
   - list membership state for a session.

3. Index:
   `actor_key`

   Supports:
   - actor membership history queries.

A standalone `session_id` index is not required because `session_id` is the leftmost prefix of the composite session/state index.

---

## 10. Critical query shapes

### Find active session for Room

```
SELECT ...
FROM CafeSession
WHERE room_ref = ?
  AND status = 'ACTIVE';
```

The partial unique index supplies both lookup and uniqueness.

### Find active participant for actor/session

```
SELECT ...
FROM CafeParticipant
WHERE session_id = ?
  AND actor_key = ?
  AND membership_state = 'ACTIVE';
```

The partial unique index supplies lookup and uniqueness.

### List active participants

```
SELECT ...
FROM CafeParticipant
WHERE session_id = ?
  AND membership_state = 'ACTIVE'
ORDER BY joined_at, participant_id;
```

The session/state index supports the critical filter.

### Find sessions requiring expiry evaluation

```
SELECT ...
FROM CafeSession
WHERE status = 'ACTIVE'
  AND expires_at <= ?;
```

The partial expiry index supports the critical filter.

### Mark session expired

Within one write transaction:

```
UPDATE CafeSession
SET status='EXPIRED',
    closed_at=NULL,
    version=version+1
WHERE session_id=?
  AND status='ACTIVE'
  AND expires_at <= ?;
```

The participant transition follows in the same transaction.

### Mark participant LEFT

```
UPDATE CafeParticipant
SET membership_state='LEFT',
    left_at=?,
    last_seen_at=?,
    version=version+1
WHERE participant_id=?
  AND actor_key=?
  AND membership_state='ACTIVE';
```

---

## 11. Transaction contract — JOIN

### 11.1 Atomic boundary

**VERIFIED**

JOIN is one database transaction.

Required logical sequence:

```
BEGIN IMMEDIATE

1. resolve/validate target session inside transaction
2. detect and transition an already-expired ACTIVE session if necessary
3. reuse the still-valid ACTIVE session OR create one
4. attempt/reuse ACTIVE participant for actor/session
5. update last_seen_at
6. update session last_activity_at
7. COMMIT
```

Authorization inputs (validated Actor, trusted Room and Telegram membership) are prerequisites to the persistence call and are not fabricated by persistence.

### 11.2 Why BEGIN IMMEDIATE

The repository's Telegram Event Ledger already uses `BEGIN IMMEDIATE` for idempotent claims.

SQLite WAL allows concurrent readers but serializes writers. A join modifies session and participant state and must not use a read-then-write sequence outside one transaction.

`BEGIN IMMEDIATE` makes the write transaction acquire the required writer reservation before the critical read/write sequence.

### 11.3 Unique constraint handling

The database constraints remain authoritative.

If a concurrent transaction wins the active-session or active-participant unique constraint:

- the losing transaction must not report a fabricated second row;
- the operation must rollback or retry according to the implementation's bounded retry policy;
- retry is allowed only after the conflicting transaction has completed;
- an unresolved persistence error is a failure, not an empty Lobby.

### 11.4 Rollback

Any SQLite error before COMMIT:

```
ROLLBACK
→ no join success
→ no fabricated session
→ no fabricated participant
```

---

## 12. Transaction contract — LEAVE

### 12.1 Atomic boundary

```
BEGIN IMMEDIATE

1. locate ACTIVE membership by participant_id + validated actor_key
2. if ACTIVE:
       transition to LEFT
       set left_at
       update last_seen_at/version
3. if already LEFT:
       return stable idempotent state
4. if EXPIRED:
       return stable expired state
5. update CafeSession.last_activity_at only when the session remains ACTIVE
6. COMMIT
```

### 12.2 Ownership

The actor cannot leave another actor's membership.

A future moderator/admin override is outside W01.

### 12.3 Idempotency

Repeated LEAVE is safe.

No second membership row is created.

No other participant is modified.

---

## 13. Concurrency contract

### 13.1 Concurrent session creation

Two concurrent JOIN requests for the same Room may both attempt to create a session.

The partial unique index guarantees that at most one ACTIVE row survives.

The implementation must not depend on a pre-check for correctness.

### 13.2 Concurrent join by same actor

Two concurrent JOIN requests for the same Actor/Session may race.

The active membership partial unique index guarantees one ACTIVE membership.

The implementation must converge on the surviving membership or perform a bounded retry.

### 13.3 Concurrent joins by different actors

Different actors may join the same ACTIVE session.

WAL permits readers to proceed while the single writer transaction is serialized.

Each join is a short write transaction.

### 13.4 Concurrent leave

LEAVE uses an ownership predicate and state predicate:

```
participant_id = ?
AND actor_key = ?
AND membership_state = 'ACTIVE'
```

Only the first successful transition changes the row.

Repeated LEAVE observes a stable non-ACTIVE state.

### 13.5 Expiry racing with JOIN

This is resolved by transaction serialization, not by wall-clock assumptions.

The rule is:

1. the transaction that acquires the write boundary first establishes the committed state;
2. JOIN must evaluate `expires_at` against the transaction's current UTC time;
3. if the session is already expired when JOIN obtains the write boundary, the session becomes EXPIRED and JOIN creates/reuses a new eligible session;
4. if JOIN commits while the session is still valid, a later expiry operation sees the committed ACTIVE session and expires it only when `expires_at <= now`.

There is no split-brain "expired and active" state because the state transition is database-serialized.

### 13.6 Retry policy

**DESIGNED**

Retries are allowed only for transient SQLite lock/busy failures and must be bounded.

A persistent SQLite error after the bounded retry budget is a persistence failure.

No infinite retry loop and no background retry daemon are part of W01.

---

## 14. Expiry semantics

### 14.1 No scheduler

**VERIFIED**

WORLD-01 does not create a scheduler or daemon.

Expiry is evaluated opportunistically by relevant reads/writes and by any already-approved cleanup mechanism.

### 14.2 Session expiry

When an ACTIVE session satisfies:

`expires_at <= now_utc`

it transitions:

```
ACTIVE → EXPIRED
```

inside a write transaction.

### 14.3 Participant expiry

All ACTIVE participants belonging to the session transition in the same transaction:

```
ACTIVE → EXPIRED
```

with:

- `left_at = NULL`;
- `last_seen_at` unchanged unless the implementation has a specific observation timestamp to record;
- `version` incremented.

EXPIRED means session lifecycle expiry, not presence timeout.

### 14.4 Join after expiry

A JOIN cannot attach to an EXPIRED session.

If the Room is eligible, a new ACTIVE session is created and the actor receives a new participant membership.

### 14.5 Participant stale policy

**UNKNOWN / DEFERRED**

W01 does not define participant inactivity expiry.

`last_seen_at` is observational membership metadata.

WORLD-02 owns future real-time presence semantics.

No heartbeat is introduced.

---

## 15. CafeParticipant membership versus presence

**VERIFIED**

`CafeParticipant` is membership state.

`last_seen_at` is the timestamp of a meaningful interaction.

It is not a heartbeat lease.

No W01 state:

- polls continuously;
- expires a member merely because time elapsed since `last_seen_at`;
- creates a presence daemon;
- opens a WebSocket.

---

## 16. Failure model

### 16.1 SQLite unavailable

```
SQLite failure
    ↓
controlled persistence failure
    ↓
NO join success
NO fabricated participant list
NO fabricated empty Lobby
```

### 16.2 Read failure

A failed participant/session query is not equivalent to zero rows.

The service must surface a controlled persistence failure.

### 16.3 Constraint failure

A unique-constraint race is handled as a concurrency condition, not as permission to create another logical row.

### 16.4 Unknown database state

If schema version, migration state or database identity cannot be validated:

```
FAIL CLOSED
```

No runtime state mutation is permitted.

---

## 17. Migration strategy

### 17.1 Existing migration system

**OBSERVED**

The repository contains Alembic and an `alembic.ini`.

The current Alembic environment targets:

`sqlite:///bot_database.db`

and `src/db/models.py::Base.metadata`.

Therefore the existing Alembic environment is for the TCG/SQLAlchemy database, not the Social World event host.

### 17.2 Consequence

**VERIFIED**

W01 must not point the existing Alembic environment at `bot_ia_events.sqlite3`.

Doing so would mix:

- TCG schema ownership;
- Social World schema ownership;
- Telegram event infrastructure.

That is not acceptable.

### 17.3 Approved migration direction

**DESIGNED**

Social World should use the existing Alembic dependency family but a **separate migration environment/history** for `bot_ia_events.sqlite3`.

The future environment must:

- target only the Social World tables;
- use a dedicated version table name such as `social_world_alembic_version`;
- not use the Telegram Event Ledger's `PRAGMA user_version`;
- not change the database `application_id`;
- not include TCG metadata;
- run explicit, reviewed migrations;
- use SQLite batch mode where a future schema change requires table recreation.

Alembic documents an independently configurable version-table name and SQLite batch migration support.

### 17.4 Why not PRAGMA user_version

**VERIFIED**

`TelegramEventLedger` already uses database-wide `user_version=1`.

The SQLite header provides one database-wide user-version integer.

Therefore Social World cannot safely maintain an independent schema version by writing that same field.

### 17.5 Migration ownership

The future Social World migration environment owns:

- creation of `CafeSession`;
- creation of `CafeParticipant`;
- their indexes and constraints;
- later Social World schema changes.

It does not own Telegram tables.

### 17.6 Migration atomicity

Each revision must be applied as an explicit transaction where SQLite supports the operation transactionally.

No partially applied Social World schema may be presented as ready.

### 17.7 Rollback expectations

Rollback must be defined per migration.

No generic promise of automatic downgrade is made.

For destructive changes, the migration must document:

- affected data;
- whether downgrade is lossless;
- required backup state;
- operational recovery path.

### 17.8 Migration location

**DESIGNED**

Future files should live under a Social World-owned migration path distinct from the current TCG Alembic revisions.

No migration file is created in W01-B.

---

## 18. Startup strategy

### 18.1 No implicit runtime bootstrap

**DESIGNED**

Normal application startup must not silently create or mutate Social World schema as an incidental side effect of constructing the service.

### 18.2 Required startup behavior

Before Social World runtime is allowed to use persistence:

1. validate database identity compatibility;
2. validate the Social World migration head;
3. apply an explicitly authorized migration operation if deployment policy permits;
4. otherwise fail startup of the Social World persistence component;
5. never fabricate an empty schema state.

### 18.3 Multiple processes

FastAPI, Telegram and Discord may access the same host.

Only one process should execute a schema migration at a time.

Runtime requests must not race an in-progress migration.

A deployment/startup gate must be used for migrations; this is a deployment concern, not a Social World background daemon.

---

## 19. Connection and lifecycle contract

Every Social World connection must:

- open the same local host file;
- set `timeout=15s` unless a later measured reason changes it;
- set `PRAGMA busy_timeout=15000`;
- set `PRAGMA foreign_keys=ON`;
- verify foreign keys are enabled;
- use WAL-compatible behavior;
- close the connection after the operation/transaction;
- never leak a live connection across unrelated requests.

Transactions must be explicit.

The existing repository pattern of short-lived SQLite connections is preserved.

### Windows lifecycle

**VERIFIED / INFERENCE**

The project has a history of Windows SQLite file-close/locking hardening and current persistence implementations explicitly close connections.

Social World must preserve that pattern.

No long-lived connection or open cursor may be retained merely for convenience.

---

## 20. Multi-process safety

### 20.1 Writers

SQLite WAL still serializes writes.

Therefore Social World must keep write transactions short.

### 20.2 Readers

Read-only operations should use short-lived connections and must not hold transactions open unnecessarily.

### 20.3 Existing Telegram writer

Telegram Event Ledger and Outbox already write to the host.

Social World cannot assume exclusive ownership of the SQLite writer slot.

The 15-second busy timeout and short explicit transactions are therefore part of the compatibility contract.

### 20.4 Physical machine boundary

SQLite WAL is valid for processes on the same machine.

A future architecture that moves these processes to different machines must re-open the persistence-host decision; W01 does not support that deployment topology.

---

## 21. Backup / recovery observations

**OBSERVED**

The repository has `SQLiteBackupManager` and `BackupService`.

The current `BackupService` explicitly backs up:

- `work/bot_ia_memory.sqlite3`;
- `work/bot_ia_sessions.sqlite3`.

It does **not** demonstrate backup coverage for `config/bot_ia_events.sqlite3`.

**UNKNOWN**

No repository evidence inspected in W01-B proves that the Telegram event host is automatically backed up.

**CONTRACT CONSEQUENCE**

Before production deployment of Social World persistence, the recovery policy for the shared event host must be explicitly closed.

This is an operational handoff requirement, not evidence that the SQLite host is structurally incompatible.

No new backup system is implemented in W01-B.

---

## 22. Observability

Social World persistence should expose domain-level outcomes to the future service layer:

- `session_created`;
- `session_reused`;
- `participant_joined`;
- `participant_reused`;
- `participant_left`;
- `session_expired`;
- `persistence_failure`.

These are observability events, not a new ledger.

The event payload may include:

- correlation identifier;
- actor key;
- room reference;
- session ID;
- operation;
- outcome;
- reason;
- UTC timestamp.

**VERIFIED**

These events must not turn `TelegramEventLedger` into generic Social World persistence.

---

## 23. Security invariants

The implementation must preserve all of the following:

1. Actor identity is derived server-side from validated Telegram identity.
2. Client-supplied `actor_key` is never authoritative.
3. Client-supplied `room_key` is never authoritative.
4. Room identity comes from the trusted context + TelegramRoomRouter path.
5. No cross-room participant visibility.
6. One ACTIVE `CafeSession` per Room.
7. One ACTIVE `CafeParticipant` per Actor/session.
8. Telegram membership remains an authorization concern outside the persistence table ownership.
9. `CafeParticipant.actor_key` is not a TCG User foreign key.
10. Persistence failure never becomes an empty successful Lobby.
11. No DELETE CASCADE removes Social World history.
12. TMA remains non-authoritative.
13. `CafeRoom` remains a projection.
14. No duplicate Telegram ledger is created.
15. No browser/WebChat/physical resource is introduced.
16. 2F-8S remains untouched.

---

## 24. Tables explicitly NOT created

WORLD-01-B does not define persistent tables for:

- `CafeRoom`;
- `CafeTable`;
- `CafeWallet`;
- `CafeActivityOwner`;
- Presence;
- scheduler state;
- character/browser state;
- TCG/drop/duel state;
- Telegram event ledger;
- Telegram outbox;
- Telegram room routing.

Migration metadata used by the future Social World migration mechanism is deployment infrastructure, not Social World domain state, and is not created in this phase.

---

## 25. API / TMA boundary

W01-B creates none of:

- `/api/v1/cafe/*`;
- Telegram initData validation;
- Trusted Launch Context implementation;
- TMA Lobby;
- inventory changes;
- runtime models;
- repositories;
- services.

Those remain later phases.

---

## 26. 2F-8S boundary

No W01-B change is permitted to:

- TaskEngine;
- TaskScheduler;
- PhysicalWebChatResourceAuthority;
- PhysicalLifecycleReconciliation;
- WebPhysicalIdentity;
- QWeb;
- Playwright;
- Supervisor;
- WebQueue;
- physical browser locks.

Social World persistence has no browser dependency.

---

## 27. Open questions

Only the following remain open for later phases:

1. Exact session TTL value.
2. Exact stale-membership/presence policy in WORLD-02.
3. Exact trusted launch reference format and launcher configuration in W01-C.
4. Exact API response/error schema.
5. Exact production backup/recovery policy for the shared event host.
6. Exact migration environment file layout when runtime implementation begins.

The following are **closed** and must not be reopened without concrete technical evidence:

- Social World host = `config/bot_ia_events.sqlite3`;
- no `cafe_rooms` table in W01;
- Telegram remains Room routing authority;
- TMA is a companion, not authority;
- Social World owns only its own tables;
- 2F-8S remains isolated.

---

## 28. Self-review

### Host

The host decision was checked against the actual repository persistence code rather than selected for convenience.

### Telegram coexistence

Telegram-owned tables were identified and explicitly excluded from Social World ownership.

### Room identity

The actual router primary key is `(chat_id, message_thread_id)`; `room_key` alone is therefore not treated as sufficient global identity.

### Session uniqueness

The contract uses a database-enforced partial unique index, not a pre-check.

### Participant uniqueness

The contract uses a database-enforced partial unique index for ACTIVE memberships.

### Rejoin

LEFT memberships are retained and rejoin creates a new membership record.

### Expiry

Expiry is a lifecycle transition, not a presence engine.

### Transactions

JOIN and LEAVE are explicitly transactional and write-serialized.

### Foreign keys

The contract requires `PRAGMA foreign_keys=ON` on every connection because SQLite enforcement is connection-scoped.

### Migration

The existing Alembic environment is not reused against the event host. A separate Social World migration history is required because `user_version` is already used by Telegram Event Ledger.

### Backup

Backup coverage for the event host is not claimed without evidence.

### Runtime

No runtime code, migration, database file, test or API is created.

---

## 29. Implementation handoff

WORLD-01-C is the next explicitly authorized phase: Telegram Auth + Trusted Launch Context.

WORLD-01-D may implement the persistence layer only after WORLD-01-C is completed and the next phase is explicitly authorized.

The implementation must preserve:

```
HOST
  config/bot_ia_events.sqlite3

OWNERSHIP
  Social World → CafeSession
  Social World → CafeParticipant
  Telegram → Telegram-owned tables

IDENTITY
  CafeSession.room_ref ← trusted server-side Room resolution
  CafeParticipant.actor_key ← validated Actor

INVARIANTS
  one ACTIVE session / Room
  one ACTIVE participant / Actor / Session

TRANSACTIONS
  JOIN → one write transaction
  LEAVE → one write transaction
  EXPIRY → one write transaction

FAILURE
  persistence failure → controlled failure
  never → fabricated empty success

LIFECYCLE
  no daemon
  no heartbeat
  no scheduler

MIGRATION
  separate Social World Alembic history
  no shared PRAGMA user_version ownership
  no Telegram table mutation
```

---

## 30. Reality Table

| Element | Estado |
|---|---|
| SQLite host decision | VERIFIED |
| Existing SQLite architecture | VERIFIED |
| CafeRoom persistence | VERIFIED |
| CafeSession schema | DESIGNED |
| CafeParticipant schema | DESIGNED |
| Constraints | DESIGNED |
| Migration | DESIGNED |
| Runtime implementation | NOT IMPLEMENTED |
| Tests | NOT RUN |
| CI | NOT RUN |
| GitHub commit | VERIFIED |
| PR | VERIFIED |

---

## 31. Evidence classification summary

| Claim | Classification |
|---|---|
| Event host is not versioned in repository | OBSERVED |
| Telegram Event Ledger uses WAL/15s timeout/FK ON/explicit transactions | OBSERVED |
| Telegram Room Router identity is (chat_id, message_thread_id) | OBSERVED |
| Existing root Alembic targets bot_database.db | OBSERVED |
| Existing backup service covers memory/sessions, not event host | OBSERVED |
| SQLite WAL permits concurrent readers with serialized writers | VERIFIED |
| SQLite FK enforcement is per connection | VERIFIED |
| SQLite user_version/application_id are database-wide header fields | VERIFIED |
| Event host can structurally host Social World tables | VERIFIED |
| Exact physical production DB state | UNKNOWN |
| Production backup coverage for event host | UNKNOWN |
| CafeSession physical table | NOT IMPLEMENTED |
| CafeParticipant physical table | NOT IMPLEMENTED |

---

## 32. Result

**COMPATIBLE**

`config/bot_ia_events.sqlite3` remains a technically suitable persistence host for Social World under the contract defined here.

The critical condition is ownership separation: Social World must add only its own tables and must not take over the Telegram database-wide identity/version metadata.

The persistence contract has been reviewed and is ready for the next explicitly authorized phase.

**READY FOR WORLD-01-C**

**STOP — no runtime implementation authorized by this document.**
