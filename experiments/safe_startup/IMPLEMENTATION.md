# Safe startup implementation target

This document is the implementation contract before promotion into `app/`.

## Sequential reader

The manager must execute installation, verification, build and startup steps one at a time. Every child process is launched with stdout/stderr captured. The reader stores the original output, exit code and step name in a diagnostic record and mirrors the latest lines into the UI without blocking Tkinter.

On the first non-zero exit, missing artifact, failed import, unexpected child exit during the health window, or other deterministic startup failure: stop the sequence immediately. Do not continue with later bots. Show the unchanged stderr/stdout in the UI with a copyable diagnostic block and write it to a local log.

## AI gating

A global AI switch controls whether any LLM provider is considered. With AI disabled, deterministic bot features start without checking Ollama or cloud APIs. With AI enabled, Ollama is the primary local backend. Cloud APIs are optional fallback providers and must never be required merely to start the manager.

An individual feature should declare whether it actually requires AI. If it does not, it must not call Ollama or a cloud API.

## Routing policy

1. deterministic rule/process when possible;
2. local Ollama when AI is needed and the task is suitable;
3. optional cloud fallback only when configured and local execution is unavailable/insufficient;
4. record provider, latency, success/failure and fallback reason.

A provider failure should be classified before fallback: authentication/configuration failures should not be retried blindly; transient network/rate-limit/service failures may move to the next allowed provider.

## Process library direction

Keep experimental process definitions under `experiments/process_library/` until their contracts and tests are stable. The production design is an indexed registry, not a giant prompt: retrieve a small candidate set using deterministic metadata/tags/state, then let the AI evaluate/rank only those candidates. The executor remains deterministic and validates allowed actions.

## Monitoring target

The dashboard should expose CPU/RAM/disk, bot process state, Ollama readiness/model, configured API health state, request counts, latency and fallback counts. Metrics refresh on a timer and must not block the UI thread.

## Promotion gate

Promote code from this experiment only after tests prove: first-error stop, exact error propagation, stdout/stderr capture, child exit detection, AI-off startup without provider checks, Ollama-only operation, optional cloud fallback, and sequential artifact verification.
