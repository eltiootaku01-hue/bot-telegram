# PC-LIMITED-09 — Resource Governor contract

Status: implementation candidate on an isolated feature branch. This document does not claim that BOT-IA meets an absolute RAM ceiling.

## Purpose and boundaries

The governor controls admission of new work. It does not terminate essential processes or interrupt an active moderation operation. P0/P1 admission is never denied by resource policy. The GUI samples once per second; worker processes read the latest published local state. An invalid or missing measurement is not interpreted as zero.

- P0: moderation and security.
- P1: critical administrative and operational actions.
- P2: ordinary interactions.
- P3: local games and secondary social activity.
- P4: non-urgent background tasks and heavy browser work.

## Decimal budget profiles

Supported settings are 1.00, 1.25, 1.50, 1.75 and 2.00 decimal GB, where one GB is 1,000,000,000 bytes. At 1.00 and 1.25 GB, P3/P4 are not admitted. At 1.50 GB, P3 may be admitted only with a valid normal measurement. At 1.75 and 2.00 GB, existing P4 work may be admitted only with a valid normal measurement. The governor does not increase established concurrency or enable a missing or blocked subsystem.

## Measurement

On Windows, the sensor enumerates the current process and all descendants. It totals their working sets for operational comparison and reports summed private commit separately. Working sets contain shared pages, so summing them may count some physical pages more than once. The sum is a reproducible process-tree indicator, not unique physical RAM ownership and not a hard operating-system limit. If any descendant cannot be measured, the sample is invalid rather than deceptively low.

The observed peak is kept for the current application session; it is not persisted as a lifetime maximum.

## Pressure and hysteresis

- Warning begins at 85% of the configured budget. New P3/P4 work stops; P2 may continue below the hard budget.
- Reducing begins at 100%. New P2/P3/P4 work is denied; P0/P1 remains allowed.
- Critical begins at 110%. The same admission restriction applies; essential processes are not killed.
- Critical recovers to Reducing after 10 consecutive samples at or below 90%.
- Reducing recovers to Warning after 10 consecutive samples at or below 80%.
- Warning recovers to Normal after 10 consecutive samples at or below 75%.

If the last published state is older than five seconds, workers treat secondary activity as unavailable. This prevents stale measurements from being represented as current health.

## Persistence and UI

Only the numeric budget and non-secret runtime metrics/status are saved in per-user local application data using atomic replacement. No credentials, tokens, prompts or message contents are written. Invalid configuration falls back to 1.00 GB and is reported. Moving the slider changes a preference only; it does not start services, network connections or external providers.

The GUI distinguishes DENTRO DEL PRESUPUESTO, REDUCIENDO CARGA, PRESUPUESTO SUPERADO, PRESUPUESTO NO VERIFICADO and MODO LIMITADO POR GATE. Body Health remains blocked. This change cannot activate Discord or absent services, and does not modify WebQueue, QWebEngine, TaskEngine, TaskScheduler or the physical WebChat authority.

## Connected entry points and explicit limit

The desktop GUI checks admission before accepting ordinary chat, local-game turns, multi-bot chains, manual browser setup, new local WebChat worker starts and heavy WebQueue persona work. Local game commands are checked again at each user action, so a visible game window does not imply that the next turn is admitted.

The live Telegram poller runs the existing raw moderation check before applying secondary-work admission. If moderation returns an action, it is handled without consulting the secondary-work gate. Otherwise, the poller classifies the update and gates it before ordinary comment analysis or adapter dispatch; inline-query work is also gated. Critical command routes and administrative order/complaint callbacks remain P1. These checks apply at the current admission boundaries; they do not alter the Telegram transport, outbox or event ledger.

**Known limitation:** this candidate does not forcibly suspend or resume an already-running WebQueue/TaskOrchestrator operation or terminate a browser process when pressure begins. The protected execution and physical WebChat authority surfaces remain untouched. Therefore, the code governs new admissions and subsequent user actions, but it does not yet prove full preemption of all in-flight P3/P4 work. That stronger pause/resume behavior needs a separately authorized, architecture-safe lifecycle gate before the feature can be considered complete.

## Validation still required

Unit tests cover budget arithmetic, policy, hysteresis, persistence, unknown sensor behavior and the worker policy. The Qt desktop integration, real Windows process-tree accounting and packaged Windows product require separate validation. Unit tests do not prove the product stays below 2 GB. Full-product measurement remains a later, separately authorized phase.
