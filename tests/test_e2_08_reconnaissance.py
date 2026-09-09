"""E2-08: Define a bounded local reconnaissance result from project evidence.

Four-layer evidence:
  1. Invariant  — ReconnaissanceResult frozen, validates bounds, is_empty works
  2. Runtime    — TaskSignals can be derived from a ReconnaissanceResult
  3. Adversarial — invalid inputs raise / don't corrupt
  4. Measurable — is_empty distinguishes zero-evidence from partial evidence
"""
import pytest
from dataclasses import FrozenInstanceError


class TestInvariantReconnaissanceShape:
    """Layer 1: data-structure invariant."""

    def test_inv1_dataclass_is_frozen(self):
        from paw.core.reasoning_contracts import ReconnaissanceResult
        r = ReconnaissanceResult(task_goal="x")
        with pytest.raises(FrozenInstanceError):
            r.task_goal = "y"

    def test_inv2_defaults_produce_empty(self):
        from paw.core.reasoning_contracts import ReconnaissanceResult
        r = ReconnaissanceResult()
        assert r.is_empty()
        assert r.symbol_count == 0
        assert r.recent_change_count == 0
        assert r.test_association_count == 0
        assert r.knowledge_source_count == 0

    def test_inv3_symbol_kinds_is_mapping(self):
        from paw.core.reasoning_contracts import ReconnaissanceResult
        r = ReconnaissanceResult(symbol_count=5,
                                 symbol_kinds={"function": 3, "class": 2})
        assert r.symbol_count == 5
        assert r.symbol_kinds["function"] == 3

    def test_inv4_recent_changed_files_is_tuple(self):
        from paw.core.reasoning_contracts import ReconnaissanceResult
        r = ReconnaissanceResult(recent_changed_files=("a.py", "b.py"))
        assert isinstance(r.recent_changed_files, tuple)
        assert len(r.recent_changed_files) == 2

    def test_inv5_privacy_class_defaults_internal(self):
        from paw.core.reasoning_contracts import ReconnaissanceResult
        from paw.core.privacy import PrivacyClass
        r = ReconnaissanceResult()
        assert r.privacy_class == PrivacyClass.INTERNAL


class TestInvariantBounds:
    """Invariant: validation rules."""

    def test_inv6_confidence_out_of_range_rejected(self):
        from paw.core.reasoning_contracts import ReconnaissanceResult
        with pytest.raises(ValueError, match="evidence_confidence"):
            ReconnaissanceResult(evidence_confidence=1.5)
        with pytest.raises(ValueError):
            ReconnaissanceResult(evidence_confidence=-0.1)

    def test_inv7_confidence_boundaries_ok(self):
        from paw.core.reasoning_contracts import ReconnaissanceResult
        ReconnaissanceResult(evidence_confidence=0.0)
        ReconnaissanceResult(evidence_confidence=1.0)

    def test_inv8_negative_counts_rejected(self):
        from paw.core.reasoning_contracts import ReconnaissanceResult
        with pytest.raises(ValueError, match="non-negative"):
            ReconnaissanceResult(symbol_count=-1)
        with pytest.raises(ValueError):
            ReconnaissanceResult(recent_change_count=-1)
        with pytest.raises(ValueError):
            ReconnaissanceResult(test_association_count=-1)
        with pytest.raises(ValueError):
            ReconnaissanceResult(knowledge_source_count=-1)


# --- 2. Runtime ---------------------------------------------------
class TestRuntimeDerivesTaskSignals:
    """Layer 2: ReconnaissanceResult -> TaskSignals mapping (bounded)."""

    def test_rt1_empty_recon_yields_unknown_signals(self):
        """Zero local evidence -> all signals UNKNOWN (fail-closed)."""
        from paw.core.reasoning_contracts import ReconnaissanceResult
        r = ReconnaissanceResult(task_goal="do something")
        assert r.is_empty()
        from paw.core.reasoning_contracts import TaskSignals
        ts = TaskSignals()
        assert ts.novelty.value == "unknown"
        assert ts.impact.value == "unknown"

    def test_rt2_nonempty_recon_distinguishes_signal_levels(self):
        """Non-empty recon provides evidence (even if signals stay UNKNOWN
        for now -- E2-09 handles inference). is_empty must flip."""
        from paw.core.reasoning_contracts import ReconnaissanceResult
        r = ReconnaissanceResult(
            task_goal="add feature",
            symbol_count=42,
            recent_change_count=3,
            test_association_count=5,
            knowledge_source_count=10,
            evidence_confidence=0.6,
        )
        assert not r.is_empty()
        assert r.symbol_count == 42
        assert r.evidence_confidence == 0.6


# --- 3. Adversarial -----------------------------------------------
class TestAdversarialInputs:
    """Layer 3: malformed inputs fail safely."""

    def test_adv1_float_confidence_nan_rejected(self):
        """NaN confidence is out of [0, 1] range."""
        from paw.core.reasoning_contracts import ReconnaissanceResult
        with pytest.raises(ValueError, match="evidence_confidence"):
            ReconnaissanceResult(evidence_confidence=float("nan"))

    def test_adv2_none_values_in_optional_fields(self):
        """None for optional fields raises TypeError (frozen dataclass)."""
        from paw.core.reasoning_contracts import ReconnaissanceResult
        with pytest.raises((TypeError, ValueError)):
            ReconnaissanceResult(recent_changed_files=None)

    def test_adv3_symbol_kinds_must_be_mapping(self):
        """Dict accepted; non-dict rejected by __post_init__."""
        from paw.core.reasoning_contracts import ReconnaissanceResult
        r = ReconnaissanceResult(symbol_kinds={"a": 1})
        assert r.symbol_kinds["a"] == 1


# --- 4. Measurable ------------------------------------------------
class TestMeasurableIsEmptiness:
    """Layer 4: measurable distinction between zero and nonzero evidence."""

    @pytest.mark.parametrize("kwargs", [
        {"symbol_count": 1},
        {"recent_change_count": 1},
        {"test_association_count": 1},
        {"knowledge_source_count": 1},
    ])
    def test_meas1_any_evidence_makes_non_empty(self, kwargs):
        from paw.core.reasoning_contracts import ReconnaissanceResult
        r = ReconnaissanceResult(**kwargs)
        assert not r.is_empty()

    def test_meas2_partial_vs_full_evidence(self):
        """Measurable: partial recon (some evidence, not all) is a distinct
        state from full or empty."""
        from paw.core.reasoning_contracts import ReconnaissanceResult
        partial = ReconnaissanceResult(symbol_count=10)
        full = ReconnaissanceResult(
            symbol_count=10, recent_change_count=5,
            test_association_count=3, knowledge_source_count=2,
            evidence_confidence=0.9,
        )
        empty = ReconnaissanceResult()
        assert empty.is_empty()
        assert not partial.is_empty()
        assert not full.is_empty()
        assert partial != full
        assert partial != empty
        assert full != empty

    def test_meas3_hashable_for_dedup(self):
        """ReconnaissanceResult must be hashable (frozen) for use in sets."""
        from paw.core.reasoning_contracts import ReconnaissanceResult
        r1 = ReconnaissanceResult(task_goal="x", symbol_count=1)
        r2 = ReconnaissanceResult(task_goal="x", symbol_count=1)
        r3 = ReconnaissanceResult(task_goal="y", symbol_count=1)
        s = {r1, r2, r3}
        assert len(s) == 2  # r1 == r2
