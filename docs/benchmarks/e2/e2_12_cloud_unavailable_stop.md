# E2-12: Stop visibly when the required cloud route is unavailable

## Contract

When the `ModelRouter` escalates the role (E2-11, fast/tools → reasoning) and
only a `local` provider stand-in is available, the router must **stop visibly**
rather than silently degrading to the local model. The returned `ModelSelection`
has `model_name=""` and a clear reason string, so the runtime can handle the
failure via its normal error path (ledger, checkpoint, escalation).

## Boundary rules

1. E2-12 only fires when E2-11 escalation occurred (i.e. `task_signals`
   contained OOD upscaling conditions: NOVEL_TASK, HIGH_IMPACT, LOW_CONFIDENCE,
   MISSING_EVIDENCE).
2. E2-12 only fires when the best available model is from the `local` provider.
3. When a non-local provider model exists (even if from a different provider
   name), E2-12 does NOT fire — the routing proceeds normally.
4. The stop is logged as `cloud_route_unavailable`.

## API

This is an internal behavior of `ModelRouter.route()` and
`ModelRouter.route_with_explain()`. No API change is required — the escalation
flag is local to the method call.

## Relationship to E2-13

E2-13 (Reject silent downgrade) extends this principle: even without E2-11
escalation, a high-impact task should not silently use a weaker model. E2-12 is
the immediate stop when no cloud route exists at all; E2-13 prevents downgrade
within the cloud tier.
