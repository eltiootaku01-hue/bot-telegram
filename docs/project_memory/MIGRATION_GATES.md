# FASE 2F-8D — MIG-0 Capability Verification & Migration Gates

## Scope

MIG-0 is observation, capability inventory, static verification, test inventory and gate definition only.

Current state:
- F-006 = DECIDED / CANDIDATE A.
- TaskOrchestrator = ACTIVE / MIGRATION PENDING.
- Playwright WebQueueManager = ACTIVE.
- QWebEngine WebChatQueueManager = ACTIVE.
- TaskEngine, TaskScheduler, WebChatTaskExecutor, WaitressSessionManager and AuthorityCore are intact.
- Supervisor execution remains disabled.
- MIG-1 through MIG-6 are not started.

No runtime migration, adapter, routing switch, executor, scheduler, TaskEngine, cookie/profile transfer or credential movement is authorized by MIG-0.

## Preconditions

Base HEAD verified as 54ea12ac70a0e9a9ebf461cb691584ee544231cd.

Protected hashes verified:
| Runtime | SHA |
|---|---|
| TaskEngine | 77c71832ec2b93cf2bd9cfd3669ad244e51c4663 |
| TaskScheduler | be89196d99cf2173bdb6b52055c5b9c7dab470b3 |
| WebChatQueueManager | 8ead4bdbd93792a25777b0976111c3fc8374526e |
| AuthorityCore | dcf960ad92d361848ffffdc848f6806ad6e338d8 |

PR #68 was OPEN / DRAFT / UNMERGED at the expected head. The GitHub connector does not expose the user's local working-tree status; remote branch/commit state is therefore the verifiable repository state used here.

## Evidence classes

CODE_EVIDENCE = current source.
TEST_EVIDENCE = existing test source and named tests.
RUNTIME_EVIDENCE = not collected for WebChat migration behavior.
GIT_HISTORY = existing repository history.
DOCUMENTATION = project memory and prior migration contract.
INFERENCE = explicitly marked conclusion from static evidence.

Static inspection does not prove Playwright/QWebEngine behavioral or operational parity.

## Capability Matrix

| # | Capability | Playwright | QWebEngine | Owner | Evidence | Runtime needed | Equivalence confidence | Action | Criticality | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Selector resolution | SelectorResolver/configured selectors | DOM selectors/provider specs | Both | CODE_EVIDENCE | Yes | LOW | ADAPT | HIGH | OBSERVED |
| 2 | DOM monitoring | waits/polling | MutationObserver + settle timer | QWeb target | CODE_EVIDENCE | Yes | LOW | KEEP/ADAPT | HIGH | OBSERVED |
| 3 | Response detection | visible response locator | assistant/body extraction | Both | CODE_EVIDENCE | Yes | LOW | ADAPT | HIGH | UNKNOWN |
| 4 | Response correlation | ticket passed through queue | ticket_id + operation_id + sequence | QWeb target | CODE_EVIDENCE | Yes | MEDIUM | KEEP/ADAPT | CRITICAL | OBSERVED |
| 5 | Send protocol | locator.fill/press | JS DOM injection/send button | Both | CODE_EVIDENCE | Yes | LOW | ADAPT | HIGH | UNKNOWN |
| 6 | Late response rejection | no equivalent public core mechanism | ticket and operation checks | QWeb/Scheduler | CODE_EVIDENCE + TEST_EVIDENCE | Yes | MEDIUM | KEEP | CRITICAL | OBSERVED |
| 7 | Navigation | Page.goto | QWebEngine navigation | Both | CODE_EVIDENCE | Yes | MEDIUM | ADAPT | HIGH | OBSERVED |
| 8 | Login state | fresh BrowserContext in core queue | persistent QWebEngineProfile | QWeb target | CODE_EVIDENCE | Yes | LOW | KEEP target | CRITICAL | UNKNOWN |
| 9 | Session persistence | no supplied storage state in core queue | persistent profile/storage | QWeb target | CODE_EVIDENCE | Yes | LOW | KEEP/ADAPT | CRITICAL | UNKNOWN |
| 10 | Cookies | no supplied state | ForcePersistentCookies | QWeb target | CODE_EVIDENCE | Yes | LOW | KEEP target | CRITICAL | UNKNOWN |
| 11 | Storage state | not supplied by core queue | persistent profile | Different mechanisms | CODE_EVIDENCE | Yes | LOW | REPLACE/ADAPT | CRITICAL | UNKNOWN |
| 12 | IndexedDB | not explicit in core queue | browser profile storage, no explicit contract | Browser profile | CODE_EVIDENCE | Yes | LOW | UNKNOWN until tested | HIGH | UNKNOWN |
| 13 | Interaction counters | per-waitress counter | no equivalent inspected | Playwright | CODE_EVIDENCE | Yes | HIGH | PORT/ADAPT | HIGH | VERIFIED |
| 14 | Soft reset | reload/goto fallback, reset at 20 | no equivalent inspected | Playwright | CODE_EVIDENCE + TEST_EVIDENCE | Yes | HIGH | PORT/ADAPT | HIGH | VERIFIED |
| 15 | Provider-specific behavior | Gemini-specific resolver | generic DOM protocol + provider specs | Both | CODE_EVIDENCE | Yes | LOW | ADAPT | CRITICAL | UNKNOWN |
| 16 | Response timeout | 10 s | 45 s ticket timeout + protocol watchdogs | Separate layers | CODE_EVIDENCE | Yes | MEDIUM | RECONCILE | CRITICAL | OBSERVED |
| 17 | Page timeout | 15 s | no named equivalent | Playwright | CODE_EVIDENCE | Yes | LOW | ADAPT | HIGH | VERIFIED |
| 18 | Navigation timeout | 20 s | no equivalent numeric policy inspected | Both | CODE_EVIDENCE | Yes | LOW | ADAPT | HIGH | UNKNOWN |
| 19 | Ticket timeout | no named ticket timeout | 45 s default | QWeb target | CODE_EVIDENCE | Yes | HIGH | KEEP/RECONCILE | CRITICAL | VERIFIED |
| 20 | Cancellation | no public per-task API in core queue | cancel_ticket + invalidation | QWeb target | CODE_EVIDENCE + TEST_EVIDENCE | Yes | MEDIUM | KEEP | CRITICAL | OBSERVED |
| 21 | operation_id | absent in core queue | monotonic browser operation id | QWeb target | CODE_EVIDENCE | Yes | HIGH | KEEP | CRITICAL | VERIFIED |
| 22 | Anti-zombie | no equivalent core mechanism demonstrated | operation_id + ticket checks | QWeb target | CODE_EVIDENCE | Yes | MEDIUM | KEEP | CRITICAL | OBSERVED |
| 23 | Circuit breaker | none in core queue | 3 failures / 10 s cooldown | QWeb target | CODE_EVIDENCE | Yes | HIGH | KEEP physical policy | HIGH | OBSERVED |
| 24 | Capacity recovery | no core signal | capacity_restored to scheduler | QWeb/Scheduler | CODE_EVIDENCE + TEST_EVIDENCE | Yes | MEDIUM | KEEP | HIGH | TESTED |
| 25 | Queue behavior | asyncio flow in TaskOrchestrator | QThread FIFO queue | Separate owners | CODE_EVIDENCE | Yes | HIGH | REPLACE | CRITICAL | OBSERVED |
| 26 | Worker behavior | asyncio worker | QThread worker | Separate runtimes | CODE_EVIDENCE | Yes | HIGH | REPLACE | HIGH | OBSERVED |
| 27 | Waitress identity | six fixed ids/pages | BotTicket.bot_name / selected bot | Both | CODE_EVIDENCE | Yes | MEDIUM | ADAPT | CRITICAL | OBSERVED |
| 28 | Task identity | no TaskEngine task_id | TaskEngine task_id/ticket compatibility | Target | CODE_EVIDENCE | Yes | HIGH | KEEP TaskEngine identity | CRITICAL | OBSERVED |
| 29 | Callback/result delivery | direct orchestrator callback | ticket_processed to scheduler/GUI | Separate paths | CODE_EVIDENCE | Yes | LOW | REPLACE | HIGH | UNKNOWN |
| 30 | Fallback behavior | per-waitress presentation fallback | queue/status errors | Separate policies | CODE_EVIDENCE | Yes | LOW | RECONCILE | HIGH | UNKNOWN |
| 31 | Failure propagation | exception to breaker/fallback/callback | worker failure to scheduler | Different semantics | CODE_EVIDENCE | Yes | MEDIUM | REPLACE | CRITICAL | UNKNOWN |
| 32 | Resource arbitration | no WEB_MESA_UNICA | Scheduler resource + physical lock | Different scopes | CODE_EVIDENCE + TEST_EVIDENCE | Yes | HIGH target | CONVERGE | CRITICAL | OBSERVED |
| 33 | GUI integration | no core GUI surface | QWebEngine/QThread/QWebChannel/Qt signals | QWeb target | CODE_EVIDENCE | Yes | HIGH structural | KEEP target | HIGH | OBSERVED |
| 34 | QWebChannel | N/A | JS bridge report | QWeb target | CODE_EVIDENCE | Yes | HIGH structural | KEEP | HIGH | VERIFIED |
| 35 | MutationObserver | N/A | observer + debounce/settle | QWeb target | CODE_EVIDENCE | Yes | HIGH structural | KEEP/ADAPT | CRITICAL | OBSERVED |
| 36 | Persistent browser profile | none in core queue | QWebEngineProfile storage/cache/cookies | QWeb target | CODE_EVIDENCE | Yes | HIGH structural | KEEP | CRITICAL | VERIFIED |
| 37 | Shutdown/recovery | idempotent pool close | QThread shutdown/circuit recovery | Both | CODE_EVIDENCE + TEST_EVIDENCE | Yes | MEDIUM | ADAPT | HIGH | TESTED |
| 38 | Concurrent request protection | six pages, no shared target lock | one active ticket guarded by WEB_MESA_UNICA | Different policies | CODE_EVIDENCE | Yes | HIGH structural | CONVERGE | CRITICAL | OBSERVED |
| 39 | Duplicate execution protection | no shared TaskEngine identity | duplicate ticket/task protections | Different mechanisms | CODE_EVIDENCE + TEST_EVIDENCE | Yes | MEDIUM | REPLACE/CONVERGE | CRITICAL | OBSERVED |
| 40 | Resource/session ownership | internal BrowserContext | GUI-owned QWebEngineProfile | Separate browser resources | CODE_EVIDENCE | Yes | LOW | ADAPT | CRITICAL | UNKNOWN |

Structural availability is not behavioral parity. No matrix row authorizes migration.

## MIG-3 Gates — FASE 2F-8E technical evidence

The gate state below is evidence about the current mechanisms. It is not a declaration that Playwright and QWebEngine are behaviorally equivalent or that migration has occurred.

| Gate | Requirement | State | Evidence |
|---|---|---|---|
| MIG-3-G01 Response Detection | required response semantics preserved | UNKNOWN | Existing Playwright/QWebEngine implementations differ; no safe real-provider parity test |
| MIG-3-G02 DOM Monitoring | mutation/settle behavior preserved | UNKNOWN | QWebEngine MutationObserver is statically present; Playwright polling is separately tested; cross-runtime parity not proven |
| MIG-3-G03 Selector Behavior | required provider selectors resolve | UNKNOWN | Playwright selector tests pass; QWebEngine provider selector parity not runtime-proven |
| MIG-3-G04 Send Protocol | provider send behavior preserved | UNKNOWN | Playwright fake-page send path is tested; QWebEngine JS/Qt send path requires real provider/browser evidence |
| MIG-3-G05 Response Correlation | response maps to exact task/request identity | TESTED | TaskEngine/Scheduler reject wrong/terminal task IDs; WebChat response parser rejects wrong ticket/bot in deterministic fake |
| MIG-3-G06 Late Response Rejection | terminal/cancelled response cannot re-open or complete a task | TESTED | Deterministic TaskEngine/Scheduler tests cover terminal and cancelled late responses; queue current-ticket absence also rejects late response |
| MIG-3-G07 Navigation | navigation/reload preserves required behavior | UNKNOWN | Playwright reload/goto behavior is tested in isolation; no safe provider parity evidence for QWebEngine |
| MIG-3-G08 Session/Login State | authenticated state survives target lifecycle | UNKNOWN | QWebEngine persistent profile exists; authenticated continuity cannot be proven without real account/session testing |
| MIG-3-G09 Cookies/Storage | required storage continuity preserved | UNKNOWN | Persistent QWebEngine profile is structurally present; no cookie/storage continuity test is safe without real session state |
| MIG-3-G10 Interaction Counter | counter semantics preserved | UNKNOWN | Playwright counter/threshold is tested; no QWebEngine equivalent demonstrated |
| MIG-3-G11 Soft Reset | reset semantics preserved | UNKNOWN | Playwright reload/goto fallback is tested; no QWebEngine equivalent demonstrated |
| MIG-3-G12 Timeout Semantics | ownership and precedence are unambiguous | OBSERVED | TaskEngine deadline is deterministic and tested; physical 10/15/20/45 s layers and 12 s TaskOrchestrator timeout remain heterogeneous, so final precedence is unresolved |
| MIG-3-G13 Cancellation | cancellation reaches physical operation safely | TESTED | TaskEngine → Scheduler → executor cancellation chain is tested with fake executor; WebQueue worker cancellation/resource release is tested separately; end-to-end browser cancellation remains unproven |
| MIG-3-G14 Operation ID / Anti-Zombie | stale browser operation cannot affect current task | OBSERVED | WebChat operation_id increments on cancellation and JS compares operation_id; deterministic monotonic invalidation is tested, but a real late JS callback race is not |
| MIG-3-G15 Provider Behavior | provider-specific behavior preserved | UNKNOWN | Gemini/provider-specific behavior has no safe real-provider parity evidence |
| MIG-3-G16 Circuit Breaker | one physical availability policy is preserved | OBSERVED | TaskOrchestrator and WebChatQueueManager breakers/recovery are independently tested; thresholds/scopes differ and equivalence is not proven |
| MIG-3-G17 Capacity Recovery | scheduler resumes after physical recovery | TESTED | WebQueue capacity_restored signal and scheduler binding/dispatch are covered by existing and new deterministic evidence; no real browser recovery required |
| MIG-3-G18 Failure Propagation | executor failure reaches lifecycle once | OBSERVED | Synthetic executor failure reaches TaskEngine.FAILED and terminal responses are discarded; callback/timeout/cancel error matrix is not fully end-to-end |
| MIG-3-G19 Duplicate Execution Protection | one request has one route/task identity | OBSERVED | Duplicate task_id, ticket_id and cancellation protections are tested independently; current GUI still has two active physical routes, so cross-route exclusivity is not proven |
| MIG-3-G20 Resource Arbitration | WebChat uses WEB_MESA_UNICA without cross-runtime races | OBSERVED | Scheduler resource arbitration and WebChatQueueManager lock are separately tested; Playwright WebQueueManager is outside that lock and quick actions bypass Scheduler |

### Identity evidence

- "task_id": TaskEngine lifecycle identity; deterministic duplicate rejection and response validation are tested.
- "ticket_id": WebChat compatibility identity; current TaskEngine WebChat executor maps task_id into ticket_id.
- "operation_id": browser-operation identity; incremented on cancellation/new injection and checked by QWeb JS.
- "session_id": WaitressSessionManager session identity; not used as TaskEngine lifecycle identity.
- "waitress_id": logical character identity; not a lifecycle identity.
- No test or implementation was introduced that aliases these identities.

### Timeout evidence

- TaskOrchestrator: 12 s worker timeout.
- Playwright: 10 s response, 15 s page, 20 s navigation.
- WebChatQueueManager: 45 s default ticket timeout.
- TaskEngine: injected-clock deadline and timeout state transition.
- TaskScheduler: no independent timeout policy identified.
- [TESTED] TaskEngine deadline expiration prevents dispatch and causes later response discard.
- [UNKNOWN] Cross-layer timeout precedence and duplicate-notification behavior remain unresolved.

### Cancellation evidence

- [TESTED] Scheduler cancellation calls the registered executor cancellation method.
- [OBSERVED] Scheduler retains an active registration until execution_finished(), allowing physical executor completion/failure to release resource ownership.
- [TESTED] Repeated TaskEngine/Scheduler cancellation is idempotent at the lifecycle level.
- [TESTED] WebChatQueueManager worker cancellation marks the ticket CANCELLED and releases WEB_MESA_UNICA without incrementing the circuit failure count.
- [UNKNOWN] A real QWebEngine/Playwright cancellation race is not executed in this phase.

### Circuit and capacity evidence

- [TESTED] WebChatQueueManager worker opens after 3 failures and half-opens after its configured 10 s cooldown.
- [TESTED] capacity_restored is emitted on half-open recovery.
- [TESTED] WebChatTaskExecutor binds that signal to TaskScheduler dispatch.
- [OBSERVED] TaskOrchestrator has a separate per-waitress 3-failure/30 s breaker.
- [UNKNOWN] The two breaker policies are not equivalent and are not unified in MIG-3.

### Quick Action evidence

- chocolatada remains LOCAL and is not a WebChat migration candidate.
- trivia remains WEBCHAT through TaskOrchestrator and currently bypasses TaskEngine/Scheduler/WEB_MESA_UNICA.
- [TESTED] A deterministic GUI callback test reproduces the existing PRESENTATION IDENTITY bug: the callback reads self._selected_bot_id at completion rather than a captured request identity.
- [DECIDED] The bug is recorded only; it is not repaired in MIG-3.

### F-007 — Clock determinism

- [OBSERVED] TaskEngine accepts an injectable timezone-aware clock.
- [OBSERVED] Authorization accepts an explicit current_time.
- [OBSERVED] ScopeLock expiration calls the module wall clock directly.
- [OBSERVED] TaskScheduler has no independent clock and delegates lifecycle deadline checks to TaskEngine.
- [TESTED] A deterministic TaskEngine clock test confirms injected creation/deadline time.
- [UNKNOWN] A single clock abstraction spanning ScopeLock, Authorization and operational runtime has not been established.
- No protected runtime was modified to unify clocks.

### F-008 — Scheduler observation sufficiency

- [OBSERVED] RuntimeObservation exposes Scheduler pending_task_ids and active_task_ids.
- [UNKNOWN] It does not expose _resource_active, _registrations, _resume_requests or _priority_streak.
- [DECIDED] Those internal structures are not promoted to public API in MIG-3.
- [UNKNOWN] Full Supervisor evidence for resource ownership, starvation bypass, wake/resume and registration state therefore remains limited to read-only pending/active snapshots.

## Existing Test Inventory

TaskOrchestrator: tests/test_task_orchestrator.py has 6 tests covering priority, 12 s timeout/fallback, per-waitress breaker, local-action bypass, callback containment and clean shutdown. It does not prove TaskScheduler parity.

Playwright WebQueueManager: tests/test_core_web_queue.py has 7 tests covering selector composition, browser args, visible locator selection, processing/soft reset, payload validation and idempotent shutdown. It does not prove QWebEngine parity.

QWebEngine WebChatQueueManager: tests/test_services_web_queue.py has 3 tests covering active cancellation/resource release, circuit recovery/capacity signaling and queued cancellation/FIFO preservation. It does not prove provider/authenticated-session parity.

TaskEngine: tests/test_task_engine.py has 19 tests covering identity, lifecycle, deadline, cancellation, late response discard, parent/child, waiting/interruption, duplicate ids and snapshots.

TaskScheduler: tests/test_task_scheduler.py has 16 tests covering priority/FIFO, WebChat exclusivity, cancellation, late responses, parent lifecycle, deadlines, duplicate execution protection and starvation bypass.

GUI: tests/test_gui_cafe_otaku.py has 91 tests, including async entrypoint, WebQueue mutex and profile/static GUI contracts. These are not migration parity tests.

Tavern: tests/test_tavern_virtual_cafe.py has 17 tests, including ticket-as-task identity, cancellation and late response behavior.

Supervisor: tests/test_supervisor_runtime_observation.py has 13 read-only runtime observation tests. It does not execute WebChat migration.

No MIG-0 test was added.

## Quick Action Inventory

Current operational callers of TaskOrchestrator.enqueue_task() were found only in CommandCenterWindow._schedule_async_quick_action().

| Action | Caller | Waitress | Payload | Priority | Callback | Timeout | Fallback | Local/WebChat | TO | Playwright WebQueue | Engine/Scheduler | Session | WEB_MESA_UNICA |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| chocolatada | _schedule_async_quick_action | cari | is_local_action=true + template response | HIGH | async GUI callback | 12 s not reached on local path | none | LOCAL | yes | no | no | no | no |
| trivia | _schedule_async_quick_action | sunna | is_local_action=false + anime-trivia prompt | MEDIUM | async GUI callback | 12 s | per-waitress fallback map | WEBCHAT | yes | yes | no | no | no |

chocolatada is not a Playwright migration candidate. trivia is the WebChat quick-action candidate.

## Identity Analysis

| Identity | Owner | Creation | Scope | Lifecycle | Persistence |
|---|---|---|---|---|---|
| task_id | TaskEngine | TaskEngine.create_task | one operational task | lifecycle state machine | TaskEngine memory |
| waitress_id | GUI/session/domain | caller/domain | logical character | independent of task | domain/session storage where applicable |
| session_id | WaitressSessionManager | session creation | one tavern session | start/expiry | SQLite active_sessions |
| ticket_id | WebChat compatibility layer | GUI/Tavern current paths | one WebChat ticket | ticket lifecycle | queue/maps; Tavern currently reuses as task_id |
| operation_id | WebChatQueueManager | browser injection | one browser operation | invalidated on cancellation/new operation | in-memory |

Tavern currently reuses ticket_id as TaskEngine task_id. This is existing compatibility behavior, not permission to create another identity. Future quick actions must use a TaskEngine-generated task_id and must not substitute waitress_id or operation_id.

## Timeout Analysis

TaskOrchestrator: 12 s worker timeout.
Playwright WebQueueManager: 10 s response, 15 s page, 20 s navigation.
WebChatQueueManager: 45 s ticket timeout by default plus protocol/DOM settle watchdogs.
TaskEngine: deadline and timeout_policy.
TaskScheduler: no independent timeout policy identified.

Ownership/precedence is unresolved. MIG-0 does not select a survivor and does not copy the 12 s timeout into TaskEngine.

## Cancellation Analysis

Static target chain:
TaskEngine → TaskScheduler → WebChatTaskExecutor → WebChatQueueManager.cancel_ticket().

TaskEngine owns lifecycle cancellation. TaskScheduler asks the executor to cancel physical work. WebChatQueueManager invalidates browser operation state and emits cancellation/failure signals.

Core Playwright WebQueueManager has no public per-task cancellation API in the inspected class. Cancellation parity is therefore not proven.

## Late Response Analysis

WebChatQueueManager rejects response/error payloads whose ticket id differs from the current ticket and increments operation_id on browser-operation cancellation. TaskEngine/Scheduler also discard responses for terminal/cancelled tasks. These are complementary protections and do not prove migrated quick-action end-to-end anti-zombie behavior.

## Interaction Counter

Playwright maintains interaction_counters[waitress_id] and triggers soft reset at 20 interactions. No equivalent QWebEngine per-waitress counter was found. MIG-3-G10 remains UNKNOWN.

## Soft Reset

Playwright soft_reset_page() reloads with PAGE_TIMEOUT_MS, falls back to goto() on failure and resets the counter. No equivalent QWebEngine per-waitress reset contract was found. MIG-3-G11 remains UNKNOWN.

## Six-Page Analysis

Playwright creates six pages in one BrowserContext, one for each fixed waitress id, with one interaction counter per id. Static code proves page-per-waitress representation but does not prove that six concurrent pages are a functional requirement. The target WebChat resource is single-use and QWebEngine has one active ticket guarded by WEB_MESA_UNICA. Do not simplify the six-page model until runtime/provider evidence proves it unnecessary.

## Session / Login / Storage

Playwright core WebQueueManager launches Chromium and creates a fresh BrowserContext; it does not receive GUI cookies, storage_state or a browser profile.

QWebEngine WebChatQueueManager configures a persistent QWebEngineProfile with persistent storage/cache paths and ForcePersistentCookies. The GUI creates the target profile under its browser profile path.

Cross-runtime authenticated continuity is UNKNOWN. No cookie values, tokens, credentials or storage secrets were read or copied.

## Circuit Breaker

TaskOrchestrator has a per-waitress breaker: 3 failures and 30 s recovery. WebChatQueueManager has a physical queue breaker: 3 failures and 10 s cooldown, with capacity restoration. Core Playwright WebQueueManager has no inspected breaker.

These policies are not proven equivalent. MIG-0 does not remove either.

## Fallback

TaskOrchestrator fallback is a presentation response after queue rejection or worker exception; it does not create another physical WebChat execution. WebChatQueueManager reports queue/error states. No retry was executed or introduced.

## Callback Identity

Status: BUG CONFIRMED / RISK.

_schedule_async_quick_action() creates a callback that reads self._selected_bot_id when completion occurs. The queued request independently stores waitress_id. A later GUI selection change can therefore present the result under another selected bot. No repair was made in MIG-0.

## Duplicate Execution

Static call graph shows quick actions on TaskOrchestrator while normal GUI WebChat/Tavern use TaskEngine/Scheduler. No code path was found that dispatches the same current quick-action request to both routes.

This does not prove future migration safety. A future migration must guarantee one routing decision, one task_id and one physical dispatch.

## Resource Arbitration

TaskScheduler defines WEB_MESA_UNICA and tests WebChat exclusivity. services.web_queue also has a WEB_MESA_UNICA lock, but that lock only coordinates WebChatQueueManager instances and does not coordinate the Playwright WebQueueManager.

Current quick actions bypass TaskScheduler and therefore do not acquire the target resource. This is a migration blocker for quick-action convergence.

## Supervisor Compatibility

The migrated target must preserve:
1. one TaskEngine lifecycle identity task_id;
2. TaskScheduler route WEBCHAT and resource WEB_MESA_UNICA;
3. WebChatTaskExecutor as the only physical handoff;
4. future Authorization and ScopeLock bindings to the same task_id;
5. RuntimeObservation as read-only observation of the converged Engine/Scheduler;
6. no direct Supervisor call to TaskOrchestrator or WebQueueManager;
7. no physical Authorization or ScopeLock enforcement in MIG-0.

## Migration Blockers

1. Real provider parity for response detection/send/correlation is UNKNOWN.
2. QWebEngine equivalents for interaction counters and soft reset are absent from inspected code.
3. Login/cookie/storage continuity is not proven.
4. Timeout precedence is heterogeneous and unresolved.
5. Quick actions currently bypass TaskEngine/Scheduler/resource arbitration.
6. Active callback has a confirmed selected-bot identity risk.
7. Circuit/fallback semantics differ between current paths.
8. No migrated quick-action end-to-end runtime evidence exists.

## Future MIG-3 Test Requirements

Provider selector/send/response cases; DOM mutation/settle; task_id/ticket_id/operation_id correlation; stale response after cancellation; navigation/reload; authenticated restart; storage/cookie continuity without exposing values; interaction counter and soft reset; timeout precedence; cancellation through Engine/Scheduler/executor; circuit recovery/capacity; one request to one task_id/route; WEB_MESA_UNICA exclusivity; GUI result presentation independent of mutable selected-bot state.

No such migration tests were executed or added in MIG-0.

## Rollback Constraints

Future rollback must preserve task identity, authenticated QWebEngineProfile, Tavern session/task relationships, quick-action presentation and one active WebChat resource owner.

Rollback must not reactivate Playwright while the target route remains active for the same request, and must not copy credentials/profile data.

## Result

MIG-0 = B — PARTIAL.

The capability inventory, gate definitions, static evidence and test inventory are sufficient for future planning, but migration-critical capabilities remain UNKNOWN and require runtime/provider evidence outside MIG-0.

This result does not approve MIG-1, MIG-2, MIG-3, MIG-4, MIG-5 or MIG-6.

## Postcheck

- Protected runtime implementations unchanged.
- TaskOrchestrator unchanged.
- WebQueueManager unchanged.
- WebChatQueueManager unchanged.
- TaskEngine, TaskScheduler, WebChatTaskExecutor, WaitressSessionManager and AuthorityCore unchanged.
- Quick Actions unchanged.
- No adapter, routing switch, second scheduler or second executor created.
- No browser launched.
- No real WebChat session touched.
- No cookies, storage_state, profiles or credentials copied.
- Supervisor execution not enabled.
- Authorization/ScopeLock physical enforcement not enabled.
- MIG-1 through MIG-6 not started.

## Historical continuity checkpoint — main@78d5

CURRENT MAIN HEAD: `1763974f4dc27fb5ea5f66452c0f9b57297aaa76`
PARENT / LAST FUNCTIONAL BASELINE: `78d5fa6d0b539991aba1ee700121404678c21e59`
CONSOLIDATION COMMIT: `1763974f4dc27fb5ea5f66452c0f9b57297aaa76`

### 2F-8R

- [TESTED] Base `2902ac7d019aac4f9d0f35d7ee578d88b1fc334b`.
- [TESTED] CI `36611033279`: Ubuntu PASS, Windows PASS, `857 passed`, code policy `violations=0`.

### 2F-8S / D3

- [IMPLEMENTED] PhysicalLifecycleReconciliation, runtime wiring, QWeb/Playwright physical adapters y suite S01-S13 están presentes en `main`.
- [TESTED] S03 actual conserva el orden D3: completar lógicamente antes de cerrar físicamente.
- [PARTIAL] CI `36631685318`: Windows `872 passed`; Ubuntu `863 passed, 9 errors` por `QWebEngine local page did not load` en runtime controlado. Code policy PASS en ambos.
- [DECIDED] Esta evidencia de test controlado no verifica autenticación real ni provider real.

### Physical architecture gate

- [DECIDED] Cada instancia de `RuntimeComponents` crea una autoridad física propia.
- [DECIDED] QWeb, Playwright y la reconciliación comparten esa instancia.
- [DECIDED] TaskEngine y TaskScheduler conservan ownership lógico/scheduling.
- [DECIDED] `_WEB_MESA_UNICA` permanece vigente hasta disponer de evidencia de equivalencia completa para retirarlo.
- [UNKNOWN] Provider autenticado, sesión real y evidencia externa de producción.

### Gate status

2F-8S no debe considerarse completamente verde mientras la evidencia cross-platform continúe con los errores QWebEngine anteriores. 2F-8T no queda autorizado por este checkpoint.
