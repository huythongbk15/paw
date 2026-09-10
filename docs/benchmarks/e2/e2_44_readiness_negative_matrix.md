# E2-44: Run the Full Readiness Negative Matrix and Prove Only Current READY Reaches Mutation

## Contract

A comprehensive negative matrix proves that **only** a current, non-stale
`READY` readiness artifact permits mutating proposals. All other readiness
levels and stale states must block.

## Matrix dimensions

| Readiness level | Stale | Mutating | Expected |
|-----------------|-------|----------|----------|
| READY | No | Yes | ALLOW |
| READY | Yes | Yes | BLOCK |
| NEEDS_RESEARCH | No | Yes (research) | ALLOW |
| NEEDS_RESEARCH | No | Yes (non-research) | BLOCK |
| NEEDS_CLARIFICATION | No | Yes | BLOCK |
| SPIKE_REQUIRED | No | Yes (research/spike) | ALLOW |
| SPIKE_REQUIRED | No | Yes (implementation) | BLOCK |
| REJECTED | No | Yes | BLOCK |

## Non-mutating bypass

Non-mutating proposals (`is_mutating=False`) bypass the readiness gate
regardless of readiness level or staleness.

## Verification

* D2: full negative matrix (8+ cases) + adversarial (stale + non-mutating) + measurable export.

