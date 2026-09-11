# Local-first findings — 2026-09-11

This note stays experimental until measured on the target Ryzen 5 5600G / 16 GB machine.

## Patterns worth evaluating

- Deterministic verification should outrank model confidence for arithmetic and other closed-form tasks.
- A local small model should not decide whether its own answer is trustworthy; route hard or unverifiable cases upward instead.
- Tool loops need hard turn limits and circuit breakers.
- Empty model output must be treated as a failure state, not as a successful answer.
- Claims such as fixed, verified, or sourced should be checked against actual tool/edit evidence before being surfaced.

## Current local target

- Ollama + qwen3:1.7b-q4_K_M
- On-demand only
- `keep_alive = 0`
- no remote API key
- no automatic resident daemon requirement

## Not yet merged into the core

The launcher still needs a first-class local/Ollama setup path, and live performance must be measured on the user's Windows PC before choosing local inference as the default.
