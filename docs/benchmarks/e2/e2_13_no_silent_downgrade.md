# E2-13: Reject silent downgrade to a weaker model for high-impact work

## Contract

When `task_signals` indicate high impact (`ImpactLevel.HIGH`, which maps to
`OODCondition.HIGH_IMPACT`), the `ModelRouter` must **not silently degrade** to
the `local` provider stand-in — even if the caller explicitly passed
`role="reasoning"` (bypassing E2-11 escalation). The router returns a visible
stop (`model_name=""`) with a clear reason, so the runtime can escalate to a
human or surface the error.

## Boundary rules

1. E2-13 fires when `HIGH_IMPACT` is in the observed OOD conditions AND
   `task_signals is not None`.
2. E2-13 fires regardless of whether E2-11 escalation happened.
3. E2-13 only blocks `local` provider — non-local providers with lower
   capability scores are handled by normal scoring (E2-06).
4. The stop is logged as `high_impact_local_downgrade_blocked`.

## Relationship to E2-12

- E2-12 fires when E2-11 escalation occurred (fast→reasoning) and only
  `local` is available.
- E2-13 fires whenever `HIGH_IMPACT` is observed and the best model is
  `local`, even if no escalation occurred (e.g. role was already `reasoning`).

## API

Internal behavior of `ModelRouter.route()` and
`ModelRouter.route_with_explain()`. No API change required.
