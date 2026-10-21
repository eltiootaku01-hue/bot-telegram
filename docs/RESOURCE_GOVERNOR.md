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

The governor drops categories in the required order: P4, then P3, then P2. P0/P1 is not disabled by the resource admission policy.

- Warning starts at 85% of the selected budget. P4 background/heavy-browser work is not admitted; P3 is still allowed when the selected profile supports games, and P2 may continue.
- Games-paused starts at 95%. New P3 and P4 work is denied; P2 may continue.
- Reducing starts at 100%. New P2/P3/P4 work is denied.
- Critical starts at 110%. The same secondary-work admission restriction applies; essential processes are not killed.
- Critical recovers to Reducing after 10 consecutive samples at or below 100%.
- Reducing recovers to Games-paused after 10 consecutive samples at or below 95%.
- Games-paused recovers to Warning after 10 consecutive samples at or below 90%.
- Warning recovers to Normal after 10 consecutive samples at or below 75%.

Escalation is immediate. Each recovery moves one stage only after the stable-sample requirement. If the last published state is older than five seconds, workers treat secondary activity as unavailable. This prevents stale measurements from being represented as current health.

## Persistence and UI

Only the numeric budget and non-secret runtime metrics/status are saved in per-user local application data using atomic replacement. No credentials, tokens, prompts or message contents are written. Invalid configuration falls back to 1.00 GB and is reported. Moving the slider changes a preference only; it does not start services, network connections or external providers.

The GUI distinguishes DENTRO DEL PRESUPUESTO, REDUCIENDO CARGA, PRESUPUESTO SUPERADO, PRESUPUESTO NO VERIFICADO and MODO LIMITADO POR GATE. Body Health remains blocked. This change cannot activate Discord or absent services, and does not modify WebQueue, QWebEngine, TaskEngine, TaskScheduler or the physical WebChat authority.

## Connected entry points and explicit limit

The desktop GUI checks admission before accepting ordinary chat, local-game turns, multi-bot chains, manual browser setup, new local WebChat worker starts and heavy WebQueue persona work. Local game commands are checked again at each user action, so a visible game window does not imply that the next turn is admitted.

The live Telegram poller runs the existing raw moderation check before applying secondary-work admission. If moderation returns an action, it is handled without consulting the secondary-work gate. Otherwise, the poller classifies the update and gates it before ordinary comment analysis or adapter dispatch; inline-query work is also gated. Critical command routes and administrative order/complaint callbacks remain P1. These checks apply at the current admission boundaries; they do not alter the Telegram transport, outbox or event ledger.

**Known limitation:** this candidate does not forcibly suspend or resume an already-running WebQueue/TaskOrchestrator operation or terminate a browser process when pressure begins. The protected execution and physical WebChat authority surfaces remain untouched. Therefore, the code governs new admissions and subsequent user actions, but it does not yet prove full preemption of all in-flight P3/P4 work. That stronger pause/resume behavior needs a separately authorized, architecture-safe lifecycle gate before the feature can be considered complete.

## Desktop bot dashboard

The “Control de Memoria” view uses a rotary Qt dial with five presets (1.00, 1.25, 1.50, 1.75 and 2.00 decimal GB). Turning it updates the saved budget, samples the sensor and refreshes action admission; it does not start external services or terminate running processes. Preset buttons use the same code path.

The dashboard displays the six profiles in `BOT_PROFILES`: Cari, Cami, Sunna, Chie, Chloe and Scarlet. Four profiles—Cari, Cami, Sunna and Chie—have entries in `MATRIX_BOT_SPECS`; those are configured for the existing sequential matrix. This is a count of GUI profiles, not proof of six independent processes or six active workers. The Telegram polling worker is separate from these character profiles.

Per-profile actions are shown only when an existing code path is identifiable:
- Every profile can be selected. The Taberna “Charla” and “Descanso” actions are enabled only when the current SQLite roster contains that profile; no missing roster entry is fabricated.
- Cari exposes the Waifu/TCG registry.
- Cami exposes the existing incidences/moderation panel.
- Chie exposes the already-existing local mini-games, subject to P3 admission.
- Matrix profiles expose “Abrir ficha” and “Iniciar desde aquí”; starting work remains P4, uses the text already prepared in the Lobby and follows existing gates.
- Chloe and Scarlet expose the existing order dialog and are not presented as configured matrix-browser workers.

Action buttons recalculate enabled/paused state from the same global budget and latest sample. P0/P1 controls remain available; P2/P3/P4 actions are disabled according to profile, pressure and data freshness. The dashboard must not label a profile “active” solely because its card is visible.

## Validation still required

Unit tests cover budget arithmetic, policy, hysteresis, persistence, unknown sensor behavior and the worker policy. The Qt desktop integration, real Windows process-tree accounting and packaged Windows product require separate validation. Unit tests do not prove the product stays below 2 GB. Full-product measurement remains a later, separately authorized phase.


## Community controller cross-reference

The separate, isolated policy engine for the proposed Telegram/Discord shared planner is documented in docs/architecture/COMMUNITY_CONTROL_POLICY.md and implemented as src/bot_ia/core/community_control.py. Its Medium and Low Resource modes constrain queue depth and per-user event admission; they are not RAM budgets. The Resource Governor remains the independent memory admission gate. Neither policy is active on live platform message paths until authorized adapter integration and focused validation are complete.
