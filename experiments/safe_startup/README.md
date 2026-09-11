# Safe startup experiment

This experiment defines a conservative installation and startup flow for the desktop Bot Manager.

## Rules

1. Perform checks and installation steps sequentially, never as a blind batch.
2. After each dependency/install/build/start step, capture stdout, stderr and exit code.
3. Verify the expected package, executable or service before continuing.
4. Stop immediately on the first startup or installation error.
5. Preserve the original error text in a local diagnostic log and show it in the desktop UI so it can be copied back for diagnosis.
6. Do not use an LLM to diagnose deterministic installation, import or executable failures.
7. Check Ollama only when AI is enabled or a local AI provider is configured.
8. Do not download an AI model automatically during bot startup.
9. External APIs are optional fallback providers; the normal bot must continue without them.
10. A failed AI provider must not prevent deterministic bot features from starting unless that provider is explicitly required by the selected feature.

## Proposed startup sequence

Runtime -> dependencies -> imports -> Ollama readiness (only when needed) -> model presence (only when needed) -> bot launch one at a time -> short health window -> dashboard.

If a child process exits during its health window, startup stops and the captured output is surfaced unchanged.

## Promotion criteria

Promote this experiment into `app/` only after tests cover:

- first-failure stop behavior;
- stdout/stderr capture;
- child-process exit detection;
- exact error propagation;
- AI-disabled startup without Ollama/API checks;
- Ollama-only startup;
- optional cloud fallback;
- sequential executable verification.

The experiment is intentionally not imported by production code until these behaviors are implemented and tested.
