# BOT-IA Analysis & Simulation MVP

## Status

Implementation candidate on an isolated feature branch. This document does not claim CI or runtime verification until GitHub reports the result.

## Commands

- `/analizar <contenido>`: requests a structured analysis from the existing configured provider manager. It does not create a provider, credential, permission, or network capability.
- `/simular <JSON>`: validates and executes a deterministic numeric scenario locally; it does not call a provider or require a library universe.

## Analysis contract

The provider must return JSON with exactly these keys:

- `objective`: non-empty string.
- `assumptions`, `unknowns`, `alternatives`, `risks`, `limitations`: non-empty arrays of non-empty strings.
- `recommendation`, `next_action`: non-empty strings.

The application derives `content_analyzed`, `evidence_available`, `evidence_references`, and `evidence_status` from the actual request and retrieved library evidence. Provider-generated reference IDs are never accepted. User-provided content is explicitly not treated as verified evidence. When no library universe is resolved, the analysis may still proceed through the configured provider, but the report states that no documentary evidence was retrieved. If no provider is configured, execution fails, or the output is invalid, the response is controlled and is not presented as a completed analysis.

The existing `IAChanOutputContract` is universe-bound and factual-response-oriented; fabricating a universe to satisfy it would violate its contract. This capability therefore validates its own structured analysis schema and reuses the existing `LocalWorkflow`, `ProviderManager`, librarian retrieval, and `EvidenceGate` where applicable.

## Simulation contract

The JSON root contains exactly `base` and `scenarios`. Base metrics are finite numbers. Each scenario contains a unique non-empty `name` and a non-empty `changes` list. Each change contains exactly `metric`, `operation`, and `value`. Metrics must exist in the base; operations are `set`, `add`, and `multiply`. A metric may appear multiple times in a scenario: each valid change is applied to the value produced by the previous change, in the exact order listed. Boolean, NaN, infinity, duplicate JSON keys, unknown fields, and non-finite results are rejected before a successful result is returned. Excessively nested JSON that causes the decoder to raise `RecursionError` is reported as a controlled `SimulationInputError`; the command returns `status="invalid"` with no scenarios published.

Every scenario starts from an independent copy of the base. Changes are applied in listed order. `absolute_difference` is the signed numeric delta `final_value - base_value`; `percentage_difference` is the signed percentage change. When the base is zero, percentage is `null` and an explicit explanation is returned.

## Integration boundaries

- Command precedence is applied in the intent classifier.
- `Router` selects a local deterministic route for simulation and the existing LLM route for analysis.
- `BotApplication.handle()` dispatches both commands before the generic workflow path, allowing simulation without a universe and analysis without a fabricated universe.
- `LocalWorkflow.execute_analysis()` uses the already configured provider manager and, only when a universe is resolved, the existing library retriever and evidence gate.
- No TaskEngine, TaskScheduler, WebQueue, physical WebChat authority, QWebEngine, Telegram security, WORLD persistence, SQLite infrastructure, or provider configuration is modified.

## Validation

Focused tests live in `tests/test_analysis_simulation_mvp.py`. Remote CI is authoritative for this branch. Local tests are not claimed unless executed in an environment with the repository checkout and its Python 3.14 dependencies.
