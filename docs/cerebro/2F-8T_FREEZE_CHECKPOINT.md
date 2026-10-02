# 2F-8T FREEZE CHECKPOINT

## CURRENT STATE

2F-8T is frozen as:

VERIFIED BLOCKER / ROOT CAUSE UNKNOWN

No further experiments are authorized from this checkpoint.

## PROVEN

- 2F-8T-E minimal QWebEngine probe: PASS.
- 2F-8T-H shadow delta: PASS.
- 2F-8T-K cross-route candidate: PASS.
- 2F-8T-K lifecycle candidate: PASS.
- 2F-8T-J diagnostic full-suite run: 863 passed, 9 errors.
- 2F-8T-L combined run: 54 passed, 1 failed, 9 errors.
- CI Ubuntu: 863 passed, 9 errors.
- CI Windows: PASS.
- K/services-core has a demonstrated QCoreApplication -> QApplication.instance() -> QWebEngineView() -> abort 134 failure sequence.

## DISPROVEN

- The evidence does not show QWebEngine is globally broken.
- The evidence does not show QWebChannel is globally broken.
- The evidence does not show the physical WebChat authority is the principal failure.
- The K/services-core abort does not, by itself, explain the full-suite load failure.
- The cleanup warning is not a demonstrated root cause.

## UNKNOWN

- Root cause of the full Linux-suite failure:
  QWebEngine local page did not load.
- Exact suite state/fixture/module interaction producing loadFinished=False.

## OPEN DIAGNOSTIC RUNS

- 36962921147 (2F-8T-I): still IN_PROGRESS; no final artifact; last observed active step is "Run focused state-producer candidates"; classified STALL SUSPECTED / INCOMPLETE.
- 36962921221 (2F-8T-M): still IN_PROGRESS; no final artifact; last observed active step is "Run production -> services -> target in fresh processes"; classified STALL SUSPECTED / INCOMPLETE.

These runs are preserved and are not to be treated as PASS.

## BLOCKER

Primary blocker:

VERIFIED BLOCKER / ROOT CAUSE UNKNOWN

## REPAIR

NO REPAIR JUSTIFIED for the principal 2F-8T load failure.

Production was not changed for this blocker.

## GIT

Main at checkpoint creation time:

d1deb58492285af0509df7a5e91d3d730fb48e74

Diagnostic PR:

#72
OPEN / DRAFT / NOT MERGED
head 383f8063c0d3d26cc81c7ab4af99c195a04958e8

No rebase, force-push, merge, or history rewrite.

## CI EVIDENCE

- 36962921149: 2F-8T-E success.
- 36962921200: 2F-8T-H success.
- 36962921157: 2F-8T-J workflow success while pytest exited 1; artifact retained diagnostic failure.
- 36962921180: 2F-8T-K workflow success; services-core candidate aborts 134 while cross-route and lifecycle candidates pass.
- 36962921204: 2F-8T-L failure.
- 36962921187: CI failure on Ubuntu, PASS on Windows.

## REOPEN CONDITION

Reopen 2F-8T only for new evidence that materially discriminates the principal blocker, such as:

- a new reproducible failure or successful reproduction under a changed relevant context;
- final evidence from the preserved I/M runs;
- new CI evidence that changes the classification;
- a relevant environment change;
- a production change directly affecting the observed phenomenon.

Do not reopen for curiosity, unsupported hypotheses, or the cleanup warning alone.

## SCOPE FREEZE

No 2F-8T-N/O.
No new QWebEngine harnesses.
No new diagnostic workflows.
No production repair by hypothesis.
No WORLD, Café Otaku, TCG, TMA, or economy work as part of 2F-8T.

