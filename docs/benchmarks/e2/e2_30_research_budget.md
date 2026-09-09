# E2-30: Research Budget and Typed Stop Condition

## Contract

Research is a bounded local activity before any model inference call. It must
respect three budgets:

| Budget | Unit | Default | Hard limit behavior |
|--------|------|---------|---------------------|
| Evidence count | items | 20 | stop with `BUDGET_EXHAUSTED` |
| Time | seconds | 300 | stop with `TIME_LIMIT` |
| Tokens | tokens | 4000 | stop with `TOKEN_LIMIT` |

## Typed stop conditions

```python
class ResearchStopReason(StrEnum):
    EVIDENCE_LIMIT = "evidence_limit"
    TIME_LIMIT = "time_limit"
    TOKEN_LIMIT = "token_limit"
    COMPLETED = "completed"
```

## ResearchBudget dataclass

```python
@dataclass(frozen=True)
class ResearchBudget:
    max_evidence_items: int = 20
    max_time_seconds: float = 300.0
    max_tokens: int = 4000
    stop_reason: ResearchStopReason = ResearchStopReason.COMPLETED
```

## Boundary rule

* Budgets are checked after each local research operation (symbol extraction,
  git scan, test association, knowledge lookup).
* Hitting any hard limit sets `stop_reason` and stops further research.
* `COMPLETED` means the research phase finished normally before any limit.
* Research budgets are **not** execution budgets (E2-15/E2-16 own those).

## Verification

* D2: runtime wiring + adversarial budget exhaustion + measurable stop reason.
