# E1-33 Revision freshness

Current contract, 2026-09-07.
Owner: `paw.knowledge.history.re_evaluate_on_revision`.

Only identical nonempty revision identifiers return stale=False with
revision_match. Missing or different identifiers return stale=True with
revision_mismatch, including when the pinned revision appears in recent_changes.
Reachability is not freshness.

recent_changes remains an accepted compatibility argument, not freshness proof.
The function does not resolve Git references, inspect dirty working trees,
validate source hashes or establish the clean-revision exit gate. Callers must
supply resolved revision identities and separately check workspace/content state.

Regression proof includes equal, missing, unrelated and ancestor revisions.
