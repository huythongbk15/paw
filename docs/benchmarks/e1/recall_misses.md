# E1-25 Review Every Recall Miss Before Changing Ranking or Thresholds

This document is the **E1-25 deliverable**. It records
the recall-miss review process: every miss from the
E1-23 measurement is reviewed *before* the runtime
changes ranking or thresholds.

## Why this contract exists

A recall miss is a signal: the runtime's heuristic
failed to recall a piece of expected evidence. The
E1-25 process is the discipline: a reviewer inspects
every miss, classifies the cause, and *only* changes
ranking / thresholds when the cause is in those layers.
Other causes (the expected evidence is unreachable;
the source files are missing; the fixture is wrong)
lead to a different change, not a heuristic tweak.

## The process

1. Run ``measure_recall`` on every E0 case.
2. For every miss, classify the cause into one of:
   - ``ranking`` — the candidate was retrieved but
     below the inclusion threshold.
   - ``threshold`` — the candidate was retrieved and
     ranked but the budget allocator dropped it.
   - ``retrieval`` — the candidate was not in the
     retrieved set.
   - ``source_missing`` — the source file referenced by
     the expected evidence is not in the repository.
   - ``fixture_wrong`` — the expected evidence's
     ``value`` is not actually present in the
     source file (a fixture bug, not a runtime bug).
3. A change to ranking / thresholds is permitted only
   when the classification is ``ranking`` or
   ``threshold``. A change to retrieval is permitted
   only when the classification is ``retrieval``. A
   change to fixtures is a doc + E0 case update, not a
   runtime change.

## Miss categories from the E1-23 measurement

The E1-23 contract is the data source. The E1-25
process is a discipline on top of the data. The
specific misses and their classifications are recorded
in the contract test as a parameter list; the test
fails if a miss is added without a classification.

## Phase 4 sync contract

This document is the **source of truth** for E1-25.
The companion contract test
`tests/test_e1_25_recall_misses_contract.py`
enforces the discipline: every recall-miss category
in the test has a documented response.