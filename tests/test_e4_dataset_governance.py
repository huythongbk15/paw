"""E4-01 through E4-09: Dataset governance for controlled adaptation."""
import hashlib
import json

import pytest

from paw.core.models import Capability
from paw.core.skills import SkillTrace
from paw.core.dataset import (
    DatasetExample,
    DatasetSplit,
    DatasetManifest,
    build_dataset,
    export_trace_to_example,
)


def make_trace(**overrides):
    return SkillTrace(
        task_id=overrides.get("task_id", "task_001"),
        revision="v1",
        source_files=overrides.get("source_files", ["src/main.py"]),
        evidence_sha="sha123",
        workflow_name=overrides.get("workflow_name", "fix-lint"),
        description="Fix lint issues",
        trigger=overrides.get("trigger", "on lint failure"),
        procedure_body=overrides.get(
            "procedure_body", "1. Run ruff\n2. Fix issues\n3. Re-run"
        ),
        capabilities=overrides.get("capabilities", [Capability.FILESYSTEM_READ]),
        allowed_tools=["execute_shell_command"],
        expected_effect="zero lint errors",
        safety_assessment="low risk",
        cost_estimate={"tokens": 100, "time_s": 30},
        is_success=overrides.get("is_success", True),
    )


class TestDatasetExample:
    def test_example_fields(self):
        """E4-04: DatasetExample has all required fields with lineage."""
        ex = DatasetExample(
            trace_id="t1", skill_name="fix-lint", skill_version="1.0.0",
            input_prompt="on lint failure", target_completion="Run ruff, fix, re-run",
            source_files=["src/main.py"], capabilities=["filesystem.read"],
            cost_estimate={"tokens": 100}, created_at="2026-09-11T00:00:00+00:00",
            redacted=True,
        )
        assert ex.trace_id == "t1"
        assert ex.redacted is True

    def test_example_to_dict(self):
        """E4-04: DatasetExample serializes to dict."""
        ex = DatasetExample(
            trace_id="t1", skill_name="s1", skill_version="1.0.0",
            input_prompt="input", target_completion="target",
            source_files=[], capabilities=[], cost_estimate={},
            created_at="2026-09-11", redacted=True,
        )
        d = ex.to_dict()
        assert d["trace_id"] == "t1"
        assert d["redacted"] is True


class TestExportFromTrace:
    def test_only_successful_traces_exported(self):
        """E4-05: Failed traces cannot be exported."""
        failed_trace = make_trace(is_success=False, task_id="t_failed")
        with pytest.raises(ValueError, match="not successful"):
            export_trace_to_example(failed_trace)

    def test_successful_trace_exports(self):
        """E4-05: Successful traces are exported as examples."""
        trace = make_trace(task_id="t_ok")
        ex = export_trace_to_example(trace)
        assert ex.trace_id == "t_ok"
        assert ex.redacted is True

    def test_export_redacts_secrets(self):
        """E4-06: Exported examples have secrets redacted."""
        trace = make_trace(
            task_id="t_secret",
            procedure_body="Run api_key=sk-123456789, then fix",
            trigger="on api_key error",
        )
        ex = export_trace_to_example(trace)
        assert "sk-123456789" not in ex.target_completion
        assert "REDACTED" in ex.target_completion

    def test_export_redacts_private_paths(self):
        """E4-06: Private paths are redacted in exported examples."""
        trace = make_trace(
            task_id="t_path",
            procedure_body="Config at /home/user/.config/app/config.yaml",
        )
        ex = export_trace_to_example(trace)
        assert "/home/user" not in ex.target_completion
        assert "[REDACTED_PATH]" in ex.target_completion


class TestDatasetSplits:
    def test_split_deterministic(self):
        """E4-08: Dataset splits are deterministic across runs."""
        examples = [
            DatasetExample(
                trace_id=f"t{i}", skill_name=f"s{i}", skill_version="1.0.0",
                input_prompt=f"prompt {i}", target_completion=f"target {i}",
                source_files=[], capabilities=[], cost_estimate={},
                created_at="2026-09-11", redacted=True,
            ) for i in range(20)
        ]
        manifest, splits, _ = build_dataset(
            examples=examples, dataset_id="ds1", version="1.0.0",
            description="test", consent_statement="consented",
            source_trace_ids=[f"t{i}" for i in range(20)],
            base_model="local-fast",
        )
        _, splits2, _ = build_dataset(
            examples=examples, dataset_id="ds1", version="1.0.0",
            description="test", consent_statement="consented",
            source_trace_ids=[f"t{i}" for i in range(20)],
            base_model="local-fast",
        )
        assert len(splits["train"]) == len(splits2["train"])
        assert len(splits["validation"]) == len(splits2["validation"])
        assert len(splits["test"]) == len(splits2["test"])

    def test_split_proportions(self):
        """E4-08: Splits are roughly 70/15/15."""
        examples = [
            DatasetExample(
                trace_id=f"t{i}", skill_name=f"s{i}", skill_version="1.0.0",
                input_prompt=f"p{i}", target_completion=f"t{i}",
                source_files=[], capabilities=[], cost_estimate={},
                created_at="2026-09-11", redacted=True,
            ) for i in range(100)
        ]
        _, splits, _ = build_dataset(
            examples=examples, dataset_id="ds1", version="1.0.0",
            description="test", consent_statement="consented",
            source_trace_ids=[f"t{i}" for i in range(100)],
            base_model="local-fast",
        )
        assert len(splits["train"]) > 50
        assert len(splits["validation"]) > 0
        assert len(splits["test"]) > 0


class TestDatasetManifest:
    def test_manifest_frozen_hash(self):
        """E4-09: Dataset manifest has a frozen content hash."""
        examples = [
            DatasetExample(
                trace_id=f"t{i}", skill_name="s", skill_version="1.0.0",
                input_prompt=f"p{i}", target_completion=f"t{i}",
                source_files=[], capabilities=[], cost_estimate={},
                created_at="2026-09-11", redacted=True,
            ) for i in range(10)
        ]
        manifest, _, _ = build_dataset(
            examples=examples, dataset_id="ds_test", version="1.0.0",
            description="test dataset",
            consent_statement="User consents to local training data",
            source_trace_ids=[f"t{i}" for i in range(10)],
            base_model="local-fast",
        )
        assert manifest.content_hash is not None
        assert len(manifest.content_hash) == 64
        assert manifest.example_count == 10
        assert manifest.dataset_id == "ds_test"

    def test_manifest_hash_reproducible(self):
        """E4-09: Same dataset produces same content hash."""
        examples = [DatasetExample(
            trace_id="t1", skill_name="s1", skill_version="1.0.0",
            input_prompt="p1", target_completion="t1",
            source_files=[], capabilities=[], cost_estimate={},
            created_at="2026-09-11", redacted=True,
        )]
        m1, _, _ = build_dataset(
            examples=examples, dataset_id="ds", version="1.0.0",
            description="d", consent_statement="c",
            source_trace_ids=["t1"], base_model="local-fast",
        )
        m2, _, _ = build_dataset(
            examples=examples, dataset_id="ds", version="1.0.0",
            description="d", consent_statement="c",
            source_trace_ids=["t1"], base_model="local-fast",
        )
        assert m1.content_hash == m2.content_hash

    def test_manifest_different_dataset_different_hash(self):
        """E4-09: Different datasets produce different hashes."""
        ex1 = DatasetExample(
            trace_id="t1", skill_name="s1", skill_version="1.0.0",
            input_prompt="p1", target_completion="t1",
            source_files=[], capabilities=[], cost_estimate={},
            created_at="2026-09-11", redacted=True,
        )
        ex2 = DatasetExample(
            trace_id="t1", skill_name="s2", skill_version="1.0.0",
            input_prompt="p1", target_completion="different",
            source_files=[], capabilities=[], cost_estimate={},
            created_at="2026-09-11", redacted=True,
        )
        m1, _, _ = build_dataset(
            examples=[ex1], dataset_id="ds", version="1.0.0",
            description="d", consent_statement="c",
            source_trace_ids=["t1"], base_model="local-fast",
        )
        m2, _, _ = build_dataset(
            examples=[ex2], dataset_id="ds", version="1.0.0",
            description="d", consent_statement="c",
            source_trace_ids=["t1"], base_model="local-fast",
        )
        assert m1.content_hash != m2.content_hash

    def test_manifest_to_dict(self):
        """E4-09: Manifest serializes with all lineage fields."""
        manifest = DatasetManifest(
            dataset_id="ds1", version="1.0.0", description="test",
            created_at="2026-09-11", content_hash="abc123",
            example_count=5, splits={"train": 3, "validation": 1, "test": 1},
            consent_statement="consent", retention_days=365,
            deletion_policy="user-initiated",
            source_trace_ids=["t1", "t2"], base_model="local-fast",
            environment={"python": "3.12"},
            excluded_trace_ids=["t3"],
        )
        d = manifest.to_dict()
        assert d["dataset_id"] == "ds1"
        assert d["content_hash"] == "abc123"
        assert d["excluded_trace_ids"] == ["t3"]


class TestDatasetConsent:
    def test_consent_required(self):
        """E4-03: Dataset requires explicit consent statement."""
        examples = [DatasetExample(
            trace_id="t1", skill_name="s", skill_version="1.0.0",
            input_prompt="p", target_completion="t",
            source_files=[], capabilities=[], cost_estimate={},
            created_at="2026-09-11", redacted=True,
        )]
        manifest, _, _ = build_dataset(
            examples=examples, dataset_id="ds", version="1.0.0",
            description="d", consent_statement="I consent to local training data",
            source_trace_ids=["t1"], base_model="local-fast",
        )
        assert "consent" in manifest.consent_statement.lower()

    def test_retention_days_recorded(self):
        """E4-03: Retention period is recorded."""
        examples = [DatasetExample(
            trace_id="t1", skill_name="s", skill_version="1.0.0",
            input_prompt="p", target_completion="t",
            source_files=[], capabilities=[], cost_estimate={},
            created_at="2026-09-11", redacted=True,
        )]
        manifest, _, _ = build_dataset(
            examples=examples, dataset_id="ds", version="1.0.0",
            description="d", consent_statement="c",
            source_trace_ids=["t1"], base_model="local-fast",
            retention_days=90,
        )
        assert manifest.retention_days == 90
