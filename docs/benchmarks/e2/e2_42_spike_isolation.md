# E2-42: Isolate/Discard Spike Effects and Return Its Evidence to the Same Decision Gate

## Contract

When a spike proposal is executed, its side effects must be isolated from the
main task state. The evidence (ExecutionObservation) is returned to the
decision gate for readiness evaluation.

## Spike isolation flag

`ProposedAction` gains `isolated: bool = False`. When `isolated=True`:
* The step is executed via `step_fn`.
* No `OperationRecord` is persisted.
* No autonomy usage is accumulated.
* No checkpoint is created.
* The `ExecutionObservation` is returned to the caller.

## Evidence return

The runtime returns the observation directly. The caller (decision gate) may
use `observation.result` or `observation.error` to update readiness.

## Backward compatibility

* Default `isolated=False` preserves existing behavior.
* The flag is opt-in; callers must explicitly request isolation.

## Verification

* D2: invariant + runtime wiring + adversarial (isolated=true skips persistence) + measurable export.

