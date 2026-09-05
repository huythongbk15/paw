"""E1-21 contract test: gate remote disclosure from the final manifest.

The contract is documented in
``docs/benchmarks/e1/remote_disclosure_gate.md``.
The test pins:

- the closed set ``DISCLOSURE_REFUSED_REASONS``;
- the happy path (PUBLIC to local) is allowed;
- the SECRET + cloud_unapproved refusal;
- the WORKSPACE + cloud refusal;
- the INTERNAL + cloud_unapproved refusal;
- the None privacy class treated as INTERNAL;
- the unknown provider_kind refusal (fail closed);
- the empty manifest path;
- the excluded list is NOT checked (only included).
"""

from __future__ import annotations

import pytest

from paw.core.context import ContextBudget
from paw.core.context_compiler import ContextCandidate, ContextManifest
from paw.core.privacy import (
    DISCLOSURE_REFUSED_REASONS,
    DisclosureResult,
    PrivacyClass,
    PROVIDER_LOCAL,
    gate_remote_disclosure,
)


def _manifest(items: list[ContextCandidate]) -> ContextManifest:
    return ContextManifest(
        task_id="t", budget=ContextBudget(), included=tuple(items),
    )


# --- 1. Closed set of refusal reasons ------------------------------


def test_disclosure_refused_reasons_is_closed_set() -> None:
    assert frozenset(
        {
            "class_workspace_remote",
            "class_secret_remote",
            "class_internal_unapproved_cloud",
            "class_none_unapproved_cloud",
            "unknown_provider_kind",
        }
    ) == DISCLOSURE_REFUSED_REASONS


# --- 2. Happy path: PUBLIC to local --------------------------------


def test_public_to_local_allowed() -> None:
    m = _manifest([
        ContextCandidate(source="x", source_id="a", content="", privacy_class=PrivacyClass.PUBLIC),
    ])
    r = gate_remote_disclosure(m, provider_kind=PROVIDER_LOCAL)
    assert r.allowed is True
    assert r.refused == ()


# --- 3. SECRET + cloud_unapproved refused ------------------------


def test_secret_to_cloud_unapproved_refused() -> None:
    m = _manifest([
        ContextCandidate(source="x", source_id="a", content="", privacy_class=PrivacyClass.SECRET),
    ])
    r = gate_remote_disclosure(m, provider_kind="cloud_unapproved")
    assert r.allowed is False
    assert len(r.refused) == 1
    cand, reason = r.refused[0]
    assert cand.source_id == "a"
    assert reason == "class_secret_remote"


# --- 4. WORKSPACE + cloud refused (only local is allowed) ------


def test_workspace_to_cloud_approved_refused() -> None:
    m = _manifest([
        ContextCandidate(source="x", source_id="a", content="", privacy_class=PrivacyClass.WORKSPACE),
    ])
    r = gate_remote_disclosure(m, provider_kind="cloud_approved")
    assert r.allowed is False
    assert r.refused[0][1] == "class_workspace_remote"


# --- 5. INTERNAL + cloud_unapproved refused ----------------------


def test_internal_to_cloud_unapproved_refused() -> None:
    m = _manifest([
        ContextCandidate(source="x", source_id="a", content="", privacy_class=PrivacyClass.INTERNAL),
    ])
    r = gate_remote_disclosure(m, provider_kind="cloud_unapproved")
    assert r.allowed is False
    assert r.refused[0][1] == "class_internal_unapproved_cloud"


# --- 6. INTERNAL + cloud_approved allowed ------------------------


def test_internal_to_cloud_approved_allowed() -> None:
    m = _manifest([
        ContextCandidate(source="x", source_id="a", content="", privacy_class=PrivacyClass.INTERNAL),
    ])
    r = gate_remote_disclosure(m, provider_kind="cloud_approved")
    assert r.allowed is True
    assert r.refused == ()


# --- 7. None privacy class treated as INTERNAL ------------------


def test_none_privacy_class_treated_as_internal() -> None:
    """A candidate without a privacy class uses the
    E1-03 default (INTERNAL). To an unapproved cloud
    it is refused."""
    m = _manifest([
        ContextCandidate(source="x", source_id="a", content="", privacy_class=None),
    ])
    r = gate_remote_disclosure(m, provider_kind="cloud_unapproved")
    assert r.allowed is False
    assert r.refused[0][1] == "class_internal_unapproved_cloud"


# --- 8. Unknown provider kind fails closed ----------------------


def test_unknown_provider_kind_fails_closed() -> None:
    m = _manifest([
        ContextCandidate(source="x", source_id="a", content="", privacy_class=PrivacyClass.PUBLIC),
    ])
    r = gate_remote_disclosure(m, provider_kind="satellite_relay")
    assert r.allowed is False
    assert r.refused[0][1] == "unknown_provider_kind"


# --- 9. Empty manifest -----------------------------------------


def test_empty_manifest_allowed() -> None:
    r = gate_remote_disclosure(_manifest([]), provider_kind="local")
    assert r.allowed is True
    assert r.refused == ()


# --- 10. Excluded list is NOT checked --------------------------


def test_excluded_list_not_checked() -> None:
    """The gate inspects ``included``, not ``excluded``.
    An excluded SECRET candidate does not count
    against the gate."""
    a = ContextCandidate(
        source="x", source_id="a", content="",
        privacy_class=PrivacyClass.PUBLIC,
    )
    b = ContextCandidate(
        source="x", source_id="b", content="",
        privacy_class=PrivacyClass.SECRET,
    )
    b.metadata["excluded_reason"] = "token_budget_exceeded"
    m = ContextManifest(
        task_id="t", budget=ContextBudget(), included=(a,), excluded=(b,),
    )
    r = gate_remote_disclosure(m, provider_kind="cloud_unapproved")
    assert r.allowed is True


# --- 11. Multiple refused items --------------------------------


def test_multiple_refused_items() -> None:
    a = ContextCandidate(source="x", source_id="a", content="", privacy_class=PrivacyClass.SECRET)
    b = ContextCandidate(source="x", source_id="b", content="", privacy_class=PrivacyClass.WORKSPACE)
    c = ContextCandidate(source="x", source_id="c", content="", privacy_class=PrivacyClass.PUBLIC)
    m = _manifest([a, b, c])
    r = gate_remote_disclosure(m, provider_kind="cloud_unapproved")
    assert r.allowed is False
    # 2 refused (a, b); c is public -> allowed.
    assert len(r.refused) == 2
    refused_ids = {cand.source_id for cand, _ in r.refused}
    assert refused_ids == {"a", "b"}


# --- 12. Determinism ------------------------------------------


def test_gate_deterministic() -> None:
    a = ContextCandidate(source="x", source_id="a", content="", privacy_class=PrivacyClass.SECRET)
    b = ContextCandidate(source="x", source_id="b", content="", privacy_class=PrivacyClass.WORKSPACE)
    m = _manifest([a, b])
    r1 = gate_remote_disclosure(m, provider_kind="cloud_unapproved")
    r2 = gate_remote_disclosure(m, provider_kind="cloud_unapproved")
    assert r1 == r2


# --- 13. DisclosureResult is frozen -----------------------------


def test_disclosure_result_is_frozen() -> None:
    import dataclasses

    r = DisclosureResult(allowed=True)
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.allowed = False  # type: ignore[misc]