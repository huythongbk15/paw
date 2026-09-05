"""PAW Knowledge — prior decisions + verification history (E1-31).

``retrieve_prior_decisions`` surfaces the prior
decisions + verification history a reviewer can cite
when reasoning about a new change. The function is
pure: same input -> same output, in the same order.

The contract is documented in
``docs/benchmarks/e1/prior_decisions_view.md``.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .changes import RecentChange
from .test_associations import TestLink


@dataclass(frozen=True)
class PriorDecision:
    """One prior decision the runtime surfaces for
    review.

    ``provenance`` is the source the decision came
    from: ``"recent_change"`` for a matched commit,
    ``"test_link"`` for a matched test association.
    """

    kind: str
    date: str
    description: str
    provenance: str
    commit_sha: str = ""
    test_qualified_name: str = ""
    source_qualified_name: str = ""


def _match(query_lower: str, *needles: str) -> bool:
    """Return True iff ``query_lower`` matches at least
    one of the needles (case-insensitive substring).
    A short query is rejected (too noisy); an empty
    query matches nothing."""
    if not query_lower or len(query_lower) < 3:
        return False
    return any(n and query_lower in n.lower() for n in needles)


def retrieve_prior_decisions(
    query: str,
    *,
    recent_changes: Iterable[RecentChange],
    test_links: Iterable[TestLink],
    max_count: int = 20,
) -> list[PriorDecision]:
    """Surface the prior decisions + verification
    history that match ``query``.

    The heuristic is keyword + symbol-name match:
    the query is matched against the commit message
    (recent_changes) and the test's qualified name
    (test_links). A match is added to the result; the
    result is sorted by date (most-recent first) and
    capped at ``max_count``.
    """
    out: list[PriorDecision] = []
    query_lower = query.strip().lower()
    for ch in recent_changes:
        if _match(
            query_lower,
            ch.message,
            ch.author,
            " ".join(ch.changed_files),
        ):
            out.append(
                PriorDecision(
                    kind="commit",
                    date=ch.date,
                    description=ch.message,
                    provenance="recent_change",
                    commit_sha=ch.sha,
                )
            )
    for tl in test_links:
        if _match(
            query_lower,
            tl.test_qualified_name,
            tl.source_qualified_name or "",
            tl.reason or "",
        ):
            out.append(
                PriorDecision(
                    kind="test",
                    date="",  # test_links do not carry a date
                    description=(
                        f"test {tl.test_qualified_name} exercises "
                        f"{tl.source_qualified_name or 'unknown'}"
                    ),
                    provenance="test_link",
                    test_qualified_name=tl.test_qualified_name,
                    source_qualified_name=tl.source_qualified_name or "",
                )
            )
    # Sort by date desc; tests (no date) sort to the end.
    out.sort(
        key=lambda p: (
            p.kind == "test",  # commits first
            p.date,
        ),
        reverse=True,
    )
    return out[:max_count]


__all__ = ["PriorDecision", "retrieve_prior_decisions"]
