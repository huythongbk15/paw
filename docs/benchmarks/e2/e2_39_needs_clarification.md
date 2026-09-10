# E2-39: Make NEEDS_CLARIFICATION Persist the Question and Wait Without Execution

## Contract

When `ImplementationReadiness` is `NEEDS_CLARIFICATION`, the runtime must
persist the pending question and return a non-success observation without
executing any mutating proposal.

## Clarification question

`ProposedAction` gains `clarification_question: str = ""`. When readiness is
`NEEDS_CLARIFICATION` and the proposal carries a non-empty question, the
runtime logs it to the ledger before returning.

## Gate behavior

```python
if proposed.is_mutating:
    if self.readiness == "NEEDS_CLARIFICATION":
        question = proposed.clarification_question or "no_question_provided"
        await log_autonomy_gate_evaluated(
            task_id, proposed.operation_id,
            "NEEDS_CLARIFICATION", question,
        )
        return ExecutionObservation(
            step_id=proposed.operation_id,
            action_id=proposed.operation_id,
            success=False,
            error=f"needs_clarification:{question}",
            resources_used=ResourceUsage(),
        )
```

## Backward compatibility

* Empty `clarification_question` yields a generic `needs_clarification:no_question_provided`.
* Default `readiness="READY"` bypasses the gate.

## Verification

* D2: invariant + runtime wiring + adversarial (empty question, non-mutating bypass) + measurable export.

