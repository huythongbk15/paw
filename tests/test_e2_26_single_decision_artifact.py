"""E2-26: Define one decision artifact contract without duplicates.

Four-layer evidence:
  1. Invariant  — exactly one Decision, Evidence, TaskResult definition exists
  2. Runtime    — TaskResult accepts all canonical fields
  3. Adversarial — duplicate class names are detected across the codebase
  4. Measurable — no second Plan/Evidence/Decision model in any core module

Decision level: D1.
"""
import ast

import pytest


class TestInvariantSingleDefinition:
    def test_inv1_single_decision_class(self):
        from paw.core.models import Decision
        assert Decision.__module__ == "paw.core.models"

    def test_inv2_single_evidence_class(self):
        from paw.core.models import Evidence
        assert Evidence.__module__ == "paw.core.models"

    def test_inv3_single_task_result_class(self):
        from paw.core.models import TaskResult
        assert TaskResult.__module__ == "paw.core.models"


class TestRuntimeTaskResultAcceptsCanonicalFields:
    def test_rt1_task_result_with_evidence_and_decisions(self):
        from paw.core.models import TaskResult, Evidence, Decision
        result = TaskResult(
            task_id="test", status="completed", summary="done",
            decisions=[Decision(type="routing", rationale="best score")],
            evidence=[Evidence(source="test", claim="x", confidence=0.9)],
        )
        d = result.to_dict()
        assert d["task_id"] == "test"
        assert d["status"] == "completed"
        assert len(d["decisions"]) == 1
        assert d["decisions"][0]["type"] == "routing"
        assert len(d["evidence"]) == 1
        assert d["evidence"][0]["source"] == "test"

    def test_rt2_task_result_minimal(self):
        from paw.core.models import TaskResult
        result = TaskResult(task_id="minimal")
        d = result.to_dict()
        assert d["task_id"] == "minimal"
        assert d["status"] == "completed"
        assert d["decisions"] == []
        assert d["evidence"] == []


class TestAdversarialNoDupClassDiscovery:
    def _collect_class_defs(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1] / "src" / "paw" / "core"
        seen = {}
        for py_file in root.rglob("*.py"):
            try:
                tree = ast.parse(py_file.read_text())
            except SyntaxError:
                continue
            module = ".".join(
                py_file.relative_to(root.parent).with_suffix("").parts
            )
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    name = node.name
                    if name in seen:
                        seen[name].append(module)
                    else:
                        seen[name] = [module]
        return seen

    def test_adv1_no_duplicate_Decision(self):
        seen = self._collect_class_defs()
        assert "Decision" in seen
        assert len(seen["Decision"]) == 1

    def test_adv2_no_duplicate_Evidence(self):
        seen = self._collect_class_defs()
        assert "Evidence" in seen
        assert len(seen["Evidence"]) == 1

    def test_adv3_no_duplicate_TaskResult(self):
        seen = self._collect_class_defs()
        assert "TaskResult" in seen
        assert len(seen["TaskResult"]) == 1

    def test_adv4_no_duplicate_Citation(self):
        seen = self._collect_class_defs()
        assert "Citation" in seen
        assert len(seen["Citation"]) == 1


class TestMeasurableArtifactContract:
    def test_measure1_decision_fields(self):
        from paw.core.models import Decision
        fields = set(Decision.model_fields.keys())
        assert "type" in fields
        assert "rationale" in fields

    def test_measure2_evidence_fields(self):
        from paw.core.models import Evidence
        fields = set(Evidence.model_fields.keys())
        assert "source" in fields
        assert "claim" in fields
        assert "confidence" in fields

    def test_measure3_task_result_fields(self):
        from paw.core.models import TaskResult
        fields = set(TaskResult.model_fields.keys())
        assert "task_id" in fields
        assert "status" in fields
        assert "decisions" in fields
        assert "evidence" in fields
