"""A negative-control case must be reported, not folded into the gate.

The foreign case set contains one deliberately-negative case: it asserts that
``class Cosine`` exists in ``vector_based.py``, where it does not (Cosine is
token-based). It is supposed to fail.

Folding it into ``min_recall`` pinned the metric at 0.00 permanently and made the
gate structurally unpassable -- not because PAW failed, but because a case that
must fail was being scored as a failure. That is a broken measurement, not a
broken system.

So a ``negative-control`` tagged case is excluded from the metric and reported
separately, and it is gated in the opposite direction: if such a case IS
recalled, that is a false green and must FAIL the run.
"""

from __future__ import annotations

from paw.bench.e1_production import _measurement_decision


def _decision(*, metric_gate: str = "PASS", recalled_controls=(), **kwargs):
    settings = {
        "dirty": False,
        "revision_unchanged": True,
        "inputs_unchanged": True,
        "tree_state_unchanged": True,
        "fixtures_fresh": True,
    }
    settings.update(kwargs)
    return _measurement_decision(
        metric_gate=metric_gate,
        recalled_controls=recalled_controls,
        **settings,
    )


class TestNegativeControlsDoNotGate:
    def test_absent_negative_control_still_passes(self):
        """The whole point: a failing control must not fail the metric."""
        decision, _reasons = _decision(recalled_controls=[])
        assert decision == "PASS"

    def test_recalled_negative_control_is_a_false_green(self):
        decision, reasons = _decision(
            recalled_controls=[{"case": "x.yaml", "outcome": "false_green"}],
        )
        assert decision == "FAIL"
        assert any("false green" in reason for reason in reasons)


class TestPrecedenceIsUnchanged:
    def test_metric_fail_still_wins(self):
        """A real metric failure is not masked by passing controls."""
        decision, _reasons = _decision(metric_gate="FAIL", recalled_controls=[])
        assert decision == "FAIL"

    def test_metric_partial_still_reported(self):
        decision, _reasons = _decision(metric_gate="PARTIAL", recalled_controls=[])
        assert decision == "PARTIAL"

    def test_dirty_tree_still_downgrades(self):
        decision, reasons = _decision(dirty=True, recalled_controls=[])
        assert decision == "PARTIAL"
        assert any("dirty tree" in reason for reason in reasons)

    def test_blocking_inputs_still_block(self):
        decision, _reasons = _decision(inputs_unchanged=False, recalled_controls=[])
        assert decision == "BLOCKED"


class TestDefaultIsSafe:
    def test_no_controls_supplied_behaves_as_before(self):
        """Existing callers that pass no controls must be unaffected."""
        decision, reasons = _measurement_decision(
            metric_gate="PASS", dirty=False, revision_unchanged=True,
            inputs_unchanged=True, tree_state_unchanged=True, fixtures_fresh=True,
        )
        assert decision == "PASS"
        assert reasons == ["metrics and provenance checks passed"]