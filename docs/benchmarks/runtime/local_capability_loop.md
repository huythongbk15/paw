# Local capability loop — design record

Decision date: 2026-10-03. Status: **design recorded, first target pinned, not
yet implemented.** No runtime code changed by this record.

## The loop

    measure  ->  diagnose  ->  change one thing  ->  measure again  ->  keep or revert

The "keep or revert" step is what makes it a loop rather than a pile of
experiments. Every change must move a measured number on a stable oracle, or it
is reverted.

| Instrument | What it measures | Stability |
|---|---|---|
| `benchmarks/runtime/run_e2e.py` | correctness of a real change, differentially | stable — fixed seed + isolated hypothesis storage |
| `benchmarks/e0/run_cloud_baseline.py` | cloud reference on the same cases | **unstable** — two runs at `temperature 0` moved the mean by ~0.10 |
| `paw.bench.e1_production` | retrieval recall | stable and fast (~12 s) |

## Where the bottleneck is, with evidence

The cloud model scores 0.00 on two cases in every run. For `public_api` that is
not the model's fault:

- `textdistance/algorithms/__init__.py` **is ingested** into PAW knowledge
  (1 chunk, 217 bytes, whole-file fallback — the AST chunker emits nothing for
  an import-only module, and the fallback covers it);
- it **never appears in the compiled manifest**. Neither local nor cloud ever
  sees it.

So the evidence that "retrieval, not the model, is the bottleneck" is not an
inference from the cloud scores. It is a direct observation: the bytes are in
the store, and the selection step leaves them out.

## First target

**Why does a 217-byte file that is the entire answer never get selected?**

Open questions, in the order they should be answered:

1. Does the chunk clear the retrieval score floor at all?
2. Is it ranked but crowded out by `max_fragments`, or is it dropped earlier?
3. Does the hybrid re-rank demote it, the way it demoted exact-lexical
   evidence elsewhere?

Each is measurable in seconds with the local retrieval path, and each has a
cheap experiment. That makes it a legitimate first iteration, unlike a model or
weight change, which would be expensive and slow to evaluate.

## First measurement: where the target is lost

Traced through every stage of the retrieval pipeline on `public_api`, with the
pool widened so that capacity could not be the cause:

| Stage | Result |
|---|---|
| chunk stored | yes — `ce3d89ba…`, 217 bytes, whole-file fallback |
| `search_chunks(limit=10)` | 10 returned, target absent |
| `search_chunks(limit=50)` | 41 returned, target **still absent** |
| `search_chunks(limit=400)` | 41 returned, target **still absent** |
| candidates after ranking | 41, target absent |
| after dedup | 37, target absent |
| after budget allocation | 30 selected / 7 excluded, target absent |

The pool is capped at 41 candidates however wide it is asked to be, and the
target is not among them at **any** limit. So the answer to question 1 is: it
never reaches ranking at all. Capacity is not the problem and never was.

**Cause.** `KnowledgeIndex.search_chunks` applies an absolute floor,
`min_score=0.1`, to a score that is a *ratio*. A long prose query pushes every
score down, so a short, sparse chunk scores 0.0682 and is discarded before any
ranking, budgeting or hybrid re-rank can consider it. The floor is not derived
from anything about the query or the corpus; it is a constant that silently
means "long questions retrieve less".

This also explains the two 0.00 cases seen against the cloud model: the model
was handed a manifest that did not contain the answer, so no model could have
answered.

## Fixing it is a decision, not a tweak

Naively lowering `min_score` is tuning the system until a benchmark clears,
which is the same anti-pattern as raising a cap. The honest framing is that the
floor is *wrong-shaped*: an absolute constant applied to a length-dependent
ratio.

Options, none taken yet:

- **Make the floor relative to the best score for this query**, keeping an
  absolute floor for genuine junk. Long queries then stop suppressing
  everything, and the decision becomes "is this chunk in the same league as the
  best match" rather than "does it clear 0.1 regardless of query length".
- **Score the provenance as well as the body.** The strongest signal for
  "which file" questions is the file path, and it is currently a small part of
  the score.
- **Record the floor-out as visible.** A chunk dropped by the floor currently
  leaves no trace, which is why this took a stage-by-stage trace to find.

This needs a decision record and a benchmark that can tell a real improvement
from a constant lowered until the numbers move.

## The decision that is not mine to make

"Training local" can mean two different things, and the evidence points away
from the expensive one:

- **Changing weights** (distillation, fine-tuning from cloud output). This is
  E4. It needs a consented dataset, a build, an evaluation gate and a rollback
  target. It is also the wrong first move while the bottleneck is retrieval,
  because a better model reading a manifest that omits the answer still fails.
- **Raising local capability** (retrieval, context assembly, routing, skills).
  Cheap, fast to evaluate, reversible, and aimed at the measured bottleneck.

Recommendation: run the loop against **retrieval first**, and only consider
weights once retrieval stops being the limiting factor. Weight changes are
irreversible in cost and slow to falsify; capability changes are neither.