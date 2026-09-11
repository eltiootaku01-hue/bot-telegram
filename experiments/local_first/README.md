# Local-first routing experiment

This experiment documents a possible next-stage routing policy before promotion into `app/`.

## Goal
Use deterministic rules and local Ollama first, while keeping cloud providers optional rather than required.

## Candidate policy
1. Rules handle obvious messages without an LLM.
2. Ollama `llama3.2:1b` handles short/social/summarization/rewrite tasks locally.
3. A stronger backend is used only when local confidence is insufficient or a task is explicitly complex.
4. Provider health is tracked independently so one failure does not disable unrelated providers.
5. Exact repeated prompts can use a short-lived local cache.

## Safety / promotion criteria
Do not promote this experiment until it has tests for routing order, local-only operation, failure isolation, and deterministic fallback behavior.

## Important
The Ollama model is intentionally not bundled into the Windows executable. It remains a separately installed local dependency.
