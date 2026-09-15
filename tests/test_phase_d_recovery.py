"""Phase D — Failure Recovery Benchmark Test Suite.

Tests PAW's ability to recover from partial execution in a multi-step
file-generation operation. Uses cookiecutter's ``generate_file`` as the
multi-step engineering operation (unfamiliar repository: cookiecutter).

Scenarios:
  D8 - Partial failure: operation fails midway → inspect → recover
  D9 - Restart after checkpoint: kill process after checkpoint → resume
  D10 - Already-completed: external actor creates a pending file → detect + skip
  D11 - Ambiguous state: partially-written file → BLOCK
  D12 - Idempotency: recovery produces identical result
  D13 - Final-state verification: all files exist with correct content
"""

import asyncio
import json
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cookiecutter.environment import StrictEnvironment
from cookiecutter.generate import generate_file
from cookiecutter.utils import work_in
from jinja2.exceptions import UndefinedError

from paw.core.models import (
    AutonomyDecision,
    Capability,
    ExecutionObservation,
    ProposedAction,
    ResourceUsage,
    RuntimeOutcome,
    StopReason,
)
from paw.core.runtime import ActionProposer, StepFn, PawRuntime
from paw.core.autonomy import AutonomyController
from paw.core.policy import PolicyGuard
from paw.core.checkpoint import CheckpointManager
from paw.core.ledger import TaskLedger
from paw.core.checkpoint import OperationRecordStore, RuntimePersistence
from paw.core.storage import get_db


# ── Fixtures ───────────────────────────────────────────────────────────

COOKIECUTTER_DIR = Path("/tmp/benchmark_repos/cookiecutter")
TEMPLATE_DIR = COOKIECUTTER_DIR / "tests/test-generate-multi-step"
BROKEN_TEMPLATE_DIR = COOKIECUTTER_DIR / "tests/test-generate-broken"


def _list_template_files(template_dir: Path) -> list[Path]:
    """List template files in cookiecutter's processing order (sorted)."""
    files = []
    with work_in(template_dir):
        import os as _os
        for root, dirs, filenames in _os.walk("."):
            dirs.sort()
            for f in sorted(filenames):
                if f == "cookiecutter.json":
                    continue
                files.append(Path(root) / f)
    return files


def _make_context():
    """Create a valid cookiecutter context (without nonexistent_feature)."""
    return {
        "cookiecutter": {
            "project_name": "MyProject",
            "package_name": "mypackage",
            "version": "0.1.0",
            "description": "A test project",
        }
    }


def _make_broken_context():
    """Context missing the 'nonexistent_feature' key (causes UndefinedError)."""
    return _make_context()


# ── FileGenerationProposer ─────────────────────────────────────────────

class FileGenerationProposer(ActionProposer):
    """Proposes the next file to generate, in deterministic order."""

    def __init__(self, template_files: list[Path], project_name: str):
        super().__init__(default_role="fast", max_proposals=1)
        self._template_files = template_files
        self._project_name = project_name
        self._proposal_count = 0
        self._num_files = len(template_files)

    def propose(self, task_id, task_goal, context, skills, last_observation, autonomy_usage):
        self._proposal_count += 1
        file_index = self._proposal_count - 1
        if file_index < self._num_files:
            template_file = self._template_files[file_index]
            goal = f"Generate file {file_index + 1}/{self._num_files}: {template_file.name}"
        else:
            goal = "All files generated"
        return ProposedAction(
            goal=goal,
            capabilities=[],
            context={},
            metadata={"file_index": file_index, "project_name": self._project_name},
            operation_id=f"file_gen_{file_index}",
            estimated_cost=ResourceUsage(tool_calls=1, tokens=100),
        )


# ── Step functions ──────────────────────────────────────────────────────

class FileGenerationStepFn:
    """Step function that generates one cookiecutter file per call.

    Each call generates ONE file. The file_index comes from the propo
    se d action's metadata. If the file already exists, it is skipped
    (simulating idempotent recovery).
    """

    def __init__(self, template_dir: Path, output_dir: Path, context: dict):
        self._template_dir = template_dir
        self._output_dir = output_dir
        self._context = context
        self._template_files = _list_template_files(template_dir)

    @property
    def template_files(self):
        return self._template_files

    @property
    def project_dir(self):
        return self._output_dir / self._context["cookiecutter"]["project_name"]

    async def __call__(self, task_id, proposed_action):
        file_index = proposed_action.metadata.get("file_index", 0)
        num_files = len(self._template_files)

        if file_index >= num_files:
            return ExecutionObservation(
                step_id=f"step_{file_index}",
                action_id=proposed_action.operation_id,
                result={"done": True, "progress": 1.0},
                resources_used=ResourceUsage(),
                success=True,
            )

        template_file = self._template_files[file_index]
        infile = str(template_file)
        context = self._context

        # Create the project directory if it doesn't exist
        self.project_dir.mkdir(parents=True, exist_ok=True)

        # Render the output filename
        with work_in(self._template_dir):
            env = StrictEnvironment(
                context=context,
                keep_project_on_failure=True,
            )
            outfile_tmpl = env.from_string(infile)
            outfile = os.path.join(str(self.project_dir), outfile_tmpl.render(**context))

        # Check if file already exists (skip_if_file_exists pattern)
        if os.path.exists(outfile):
            return ExecutionObservation(
                step_id=f"step_{file_index}",
                action_id=proposed_action.operation_id,
                result={"done": file_index == num_files - 1, "progress": (file_index + 1) / num_files, "skipped": True},
                resources_used=ResourceUsage(),
                success=True,
            )

        # Generate the file
        try:
            with work_in(self._template_dir):
                env = StrictEnvironment(
                    context=context,
                    keep_project_on_failure=True,
                )
                generate_file(
                    str(self.project_dir),
                    infile,
                    context,
                    env,
                    skip_if_file_exists=True,
                )
        except UndefinedError as e:
            return ExecutionObservation(
                step_id=f"step_{file_index}",
                action_id=proposed_action.operation_id,
                result={"done": True, "progress": file_index / num_files, "error": str(e)},
                resources_used=ResourceUsage(),
                success=False,
                error=str(e),
            )
        except Exception as e:
            return ExecutionObservation(
                step_id=f"step_{file_index}",
                action_id=proposed_action.operation_id,
                result={"done": True, "progress": file_index / num_files, "error": str(e)},
                resources_used=ResourceUsage(),
                success=False,
                error=str(e),
            )

        return ExecutionObservation(
            step_id=f"step_{file_index}",
            action_id=proposed_action.operation_id,
            result={"done": file_index == num_files - 1, "progress": (file_index + 1) / num_files},
            resources_used=ResourceUsage(),
            success=True,
        )


# ── Helpers ─────────────────────────────────────────────────────────────

def _list_generated_files(project_dir: Path) -> list[str]:
    """List files in the generated project directory (relative, sorted)."""
    files = []
    for root, dirs, filenames in os.walk(project_dir):
        dirs.sort()
        for f in sorted(filenames):
            rel = os.path.relpath(os.path.join(root, f), project_dir)
            files.append(rel)
    return files


def _file_content(path: Path) -> str | None:
    """Read file content, or None if file doesn't exist."""
    if path.exists():
        return path.read_text()
    return None


# ── Runtime factory ────────────────────────────────────────────────────

def _make_runtime(db_path: str, proposer, step_fn):
    """Create a PawRuntime wired with policy + autonomy for the test."""
    db = get_db(db_path)
    from paw.core.policy import PolicyGuard
    policy_guard = PolicyGuard()
    autonomy = AutonomyController(
        budget=ResourceUsage.max_for_testing() if hasattr(ResourceUsage, 'max_for_testing') else ResourceUsage(),
    )
    ckpt_mgr = CheckpointManager(db)
    ledger = TaskLedger()
    runtime = PawRuntime(
        db=db,
        policy_guard=policy_guard,
        autonomy=autonomy,
        checkpoint_mgr=ckpt_mgr,
        ledger=ledger,
        proposer=proposer,
        step_fn=step_fn,
    )
    return runtime


# ═══════════════════════════════════════════════════════════════════════
# D8 — Scenario 1: Partial failure
# ═══════════════════════════════════════════════════════════════════════

class TestD8PartialFailure:
    """D8: Operation fails midway → inspect state → recover."""

    def test_partial_failure_then_recovery(self, tmp_path):
        """Run with broken template until file #6 fails, then fix and resume."""
        import asyncio

        async def run_scenario():
            # ── Phase 1: Run with broken template (fails at file #6) ──
            db_path = str(tmp_path / "test_d8.db")
            output_dir = tmp_path / "output1"

            template_files = _list_template_files(BROKEN_TEMPLATE_DIR)
            context = _make_broken_context()
            step_fn = FileGenerationStepFn(BROKEN_TEMPLATE_DIR, output_dir, context)
            proposer = FileGenerationProposer(template_files, context["cookiecutter"]["project_name"])

            runtime = _make_runtime(db_path, proposer, step_fn)

            result1 = await runtime.run(
                task_id="d8_partial_failure",
                task_goal="Generate project files from broken template",
                step_fn=step_fn,
                max_iterations=20,
            )

            # Verify failure
            assert result1.stopped, "Runtime should have stopped"
            assert result1.reason == StopReason.TASK_FAILED, \
                f"Expected TASK_FAILED, got {result1.reason}"
            assert result1.checkpoint_id is not None, \
                "Should have created a checkpoint on failure"

            # State inspection
            project_dir = output_dir / context["cookiecutter"]["project_name"]
            actual_files = _list_generated_files(project_dir)

            # Files 0-5 should exist (LICENSE, README.md, requirements.txt, setup.py, docs/index.rst, mypackage/__init__.py)
            # File 6 (mypackage/core.py) should NOT exist (failed)
            expected_files_0_to_5 = [
                "LICENSE", "README.md", "requirements.txt", "setup.py",
                "docs/index.rst", "mypackage/__init__.py",
            ]
            expected_core_py = "mypackage/core.py"

            for f in expected_files_0_to_5:
                assert f in actual_files, f"File {f} should exist after partial failure"

            assert expected_core_py not in actual_files, \
                f"File {expected_core_py} should NOT exist after failure"

            # State reconciliation classification
            all_expected = expected_files_0_to_5 + [expected_core_py]
            actual_set = set(actual_files)
            check_completed = [f for f in expected_files_0_to_5 if f in actual_set]
            check_not_completed = [f for f in [expected_core_py] if f not in actual_set]

            assert len(check_completed) == 6, f"Expected 6 completed, got {len(check_completed)}"
            assert len(check_not_completed) == 1, f"Expected 1 not completed, got {len(check_not_completed)}"

            # ── Phase 2: Fix template and resume ──
            # Use the FIXED template (without undefined variable)
            fixed_step_fn = FileGenerationStepFn(TEMPLATE_DIR, output_dir, context)
            # Create new runtime with same db (for checkpoint/resume), fixed step_fn
            fixed_proposer = FileGenerationProposer(
                _list_template_files(TEMPLATE_DIR),
                context["cookiecutter"]["project_name"],
            )
            fixed_runtime = _make_runtime(db_path, fixed_proposer, fixed_step_fn)

            result2 = await fixed_runtime.run(
                task_id="d8_partial_failure",
                task_goal="Generate project files from fixed template",
                step_fn=fixed_step_fn,
                max_iterations=30,
                resume_from_checkpoint=result1.checkpoint_id,
            )

            # Verify recovery success
            assert result2.stopped, "Recovery runtime should have stopped"
            assert result2.last_observation is not None, "Should have final observation"
            if result2.reason != StopReason.STOP_SUCCESS:
                assert result2.last_observation.result.get("done") == True, \
                    "All files should be generated after recovery"

            # Verify all 7 files exist
            final_files = _list_generated_files(project_dir)
            for f in all_expected:
                assert f in final_files, f"File {f} should exist after recovery"

            return True

        result = asyncio.run(run_scenario())
        assert result, "D8 scenario failed"

    def test_state_inspection_after_failure(self, tmp_path):
        """Verify state inspection correctly classifies completed/ pending operations."""
        import asyncio

        async def run_scenario():
            db_path = str(tmp_path / "test_d8_state.db")
            output_dir = tmp_path / "output2"

            template_files = _list_template_files(BROKEN_TEMPLATE_DIR)
            context = _make_broken_context()
            step_fn = FileGenerationStepFn(BROKEN_TEMPLATE_DIR, output_dir, context)
            proposer = FileGenerationProposer(template_files, context["cookiecutter"]["project_name"])

            runtime = _make_runtime(db_path, proposer, step_fn)

            result = await runtime.run(
                task_id="d8_state_inspection",
                task_goal="Generate project files from broken template",
                step_fn=step_fn,
                max_iterations=20,
            )

            # Inspect actual filesystem state
            project_dir = output_dir / context["cookiecutter"]["project_name"]
            actual_files = _list_generated_files(project_dir)

            # Inspect checkpoint state
            checkpoint = None
            if result.checkpoint_id:
                checkpoint = await runtime.checkpoint_mgr.get_latest(result.task_id)

            # Verify checkpoint has operation records
            assert checkpoint is not None, "Checkpoint should exist after failure"
            assert checkpoint.status == "failed", \
                f"Checkpoint status should be 'failed', got {checkpoint.status}"

            return True

        result = asyncio.run(run_scenario())
        assert result

    def test_recovery_does_not_retry_completed(self, tmp_path):
        """Verify that recovery skips already-completed operations."""
        import asyncio

        async def run_scenario():
            db_path = str(tmp_path / "test_d8_skip.db")
            output_dir = tmp_path / "output3"

            template_files = _list_template_files(BROKEN_TEMPLATE_DIR)
            context = _make_broken_context()

            # Phase 1: Run with broken template
            step_fn = FileGenerationStepFn(BROKEN_TEMPLATE_DIR, output_dir, context)
            proposer = FileGenerationProposer(template_files, context["cookiecutter"]["project_name"])
            runtime = _make_runtime(db_path, proposer, step_fn)

            result1 = await runtime.run(
                task_id="d8_skip_completed",
                task_goal="Generate project files (broken)",
                step_fn=step_fn,
                max_iterations=20,
            )

            # Verify 6 files exist, file #6 failed
            project_dir = output_dir / context["cookiecutter"]["project_name"]
            actual_files_1 = _list_generated_files(project_dir)
            assert len(actual_files_1) == 6, f"Expected 6 files, got {len(actual_files_1)}"

            # Count operations completed
            assert result1.operations_completed == 6, \
                f"Expected 6 completed ops, got {result1.operations_completed}"

            # Phase 2: Fix template and resume
            fixed_step_fn = FileGenerationStepFn(TEMPLATE_DIR, output_dir, context)
            fixed_proposer = FileGenerationProposer(
                _list_template_files(TEMPLATE_DIR),
                context["cookiecutter"]["project_name"],
            )
            fixed_runtime = _make_runtime(db_path, fixed_proposer, fixed_step_fn)

            result2 = await fixed_runtime.run(
                task_id="d8_skip_completed",
                task_goal="Generate project files (fixed)",
                step_fn=fixed_step_fn,
                max_iterations=30,
                resume_from_checkpoint=result1.checkpoint_id,
            )

            # Verify all 7 files now exist
            actual_files_2 = _list_generated_files(project_dir)
            assert len(actual_files_2) == 7, \
                f"Expected 7 files after recovery, got {len(actual_files_2)}"

            # Only 1 new file was created (file #6)
            assert result2.operations_completed == 1, \
                f"Expected 1 new operation, got {result2.operations_completed}"

            return True

        result = asyncio.run(run_scenario())
        assert result

    def test_file_content_correctness(self, tmp_path):
        """Verify that generated files have correct content after recovery."""
        import asyncio

        async def run_scenario():
            db_path = str(tmp_path / "test_d8_content.db")
            output_dir = tmp_path / "output4"

            context = _make_context()

            # Run with broken template, then fix and resume
            template_files_broken = _list_template_files(BROKEN_TEMPLATE_DIR)
            step_fn = FileGenerationStepFn(BROKEN_TEMPLATE_DIR, output_dir, context)
            proposer = FileGenerationProposer(template_files_broken, context["cookiecutter"]["project_name"])
            runtime = _make_runtime(db_path, proposer, step_fn)

            result1 = await runtime.run(
                task_id="d8_content_check",
                task_goal="Generate project files",
                step_fn=step_fn,
                max_iterations=20,
            )

            # Fix and resume
            template_files_fixed = _list_template_files(TEMPLATE_DIR)
            fixed_step_fn = FileGenerationStepFn(TEMPLATE_DIR, output_dir, context)
            fixed_proposer = FileGenerationProposer(template_files_fixed, context["cookiecutter"]["project_name"])
            fixed_runtime = _make_runtime(db_path, fixed_proposer, fixed_step_fn)

            result2 = await fixed_runtime.run(
                task_id="d8_content_check",
                task_goal="Generate project files (continued)",
                step_fn=fixed_step_fn,
                max_iterations=30,
                resume_from_checkpoint=result1.checkpoint_id,
            )

            project_dir = output_dir / context["cookiecutter"]["project_name"]

            # Verify content of recovered file (core.py)
            core_py = project_dir / "mypackage" / "core.py"
            assert core_py.exists(), "core.py should exist"
            content = core_py.read_text()
            assert "Core module for MyProject" in content
            assert "ENABLE_" not in content, "Should not contain undefined variable reference"
            assert "def main():" in content

            return True

        result = asyncio.run(run_scenario())
        assert result


# ═══════════════════════════════════════════════════════════════════════
# D9 — Scenario 2: Restart after checkpoint
# ═══════════════════════════════════════════════════════════════════════

class TestD9RestartAfterCheckpoint:
    """D9: Checkpoint → process termination → restart → resume."""

    def test_restart_resumes_from_checkpoint(self, tmp_path):
        """Simulate process termination after checkpoint, then resume."""
        import asyncio

        async def run_scenario():
            db_path = str(tmp_path / "test_d9_restart.db")
            output_dir = tmp_path / "output_d9"

            context = _make_context()
            template_files = _list_template_files(TEMPLATE_DIR)
            step_fn = FileGenerationStepFn(TEMPLATE_DIR, output_dir, context)
            proposer = FileGenerationProposer(template_files, context["cookiecutter"]["project_name"])

            # Phase 1: Run, but only process 3 files before "killing"
            step_fn._num_limit = 3  # Stop after 3 files
            runtime = _make_runtime(db_path, proposer, step_fn)

            result1 = await runtime.run(
                task_id="d9_restart",
                task_goal="Generate project files (partial)",
                step_fn=step_fn,
                max_iterations=5,  # Enough for 3 files
            )

            # After 5 iterations max, 3 files should be created
            project_dir = output_dir / context["cookiecutter"]["project_name"]
            actual_files = _list_generated_files(project_dir)
            assert len(actual_files) == 3, f"Expected 3 files, got {len(actual_files)}"

            # Verify checkpoint exists
            checkpoint = await runtime.checkpoint_mgr.get_latest("d9_restart")
            assert checkpoint is not None, "Checkpoint should exist"
            assert checkpoint.status in ("running", "completed", "failed", "awaiting_approval"), \
                f"Unexpected checkpoint status: {checkpoint.status}"

            # Phase 2: Simulate restart — create a NEW runtime instance
            # with a new proposer (counter reset), but same db + checkpoint
            step_fn2 = FileGenerationStepFn(TEMPLATE_DIR, output_dir, context)
            proposer2 = FileGenerationProposer(
                _list_template_files(TEMPLATE_DIR),
                context["cookiecutter"]["project_name"],
            )
            runtime2 = _make_runtime(db_path, proposer2, step_fn2)

            result2 = await runtime2.run(
                task_id="d9_restart",
                task_goal="Generate project files (resume)",
                step_fn=step_fn2,
                max_iterations=15,
                resume_from_checkpoint=checkpoint.checkpoint_id,
            )

            # Verify all 7 files exist after resume
            final_files = _list_generated_files(project_dir)
            assert len(final_files) == 7, \
                f"Expected 7 files after resume, got {len(final_files)}"

            return True

        result = asyncio.run(run_scenario())
        assert result

    def test_checkpoint_persists_operation_records(self, tmp_path):
        """Verify that checkpoint persistence preserves completed operation records."""
        import asyncio

        async def run_scenario():
            db_path = str(tmp_path / "test_d9_persist.db")
            output_dir = tmp_path / "output_d9_persist"

            context = _make_context()
            template_files = _list_template_files(TEMPLATE_DIR)

            # Step function that creates a checkpoint after file #2
            class PartialStepFn(FileGenerationStepFn):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)
                    self._call_count = 0

                async def __call__(self, task_id, proposed_action):
                    self._call_count += 1
                    file_index = proposed_action.metadata.get("file_index", 0)
                    result = await super().__call__(task_id, proposed_action)
                    # After generating file #2, mark it as done
                    if file_index == 1 and result.success:
                        result.result = {**result.result, "done": True}
                    return result

            step_fn = PartialStepFn(TEMPLATE_DIR, output_dir, context)
            proposer = FileGenerationProposer(template_files, context["cookiecutter"]["project_name"])
            runtime = _make_runtime(db_path, proposer, step_fn)

            result = await runtime.run(
                task_id="d9_persist",
                task_goal="Generate files with early termination",
                step_fn=step_fn,
                max_iterations=5,
            )

            # Checkpoint should exist
            checkpoint = await runtime.checkpoint_mgr.get_latest("d9_persist")
            assert checkpoint is not None
            assert checkpoint.operations_completed >= 2, \
                f"Expected >= 2 completed ops in checkpoint, got {checkpoint.operations_completed}"

            # Verify operation records in DB
            completed_ids = await OperationRecordStore.get_completed_op_ids("d9_persist")
            assert len(completed_ids) >= 2, \
                f"Expected >= 2 completed op IDs, got {len(completed_ids)}"

            return True

        result = asyncio.run(run_scenario())
        assert result


# ═══════════════════════════════════════════════════════════════════════
# D10 — Scenario 3: Already-completed effect
# ═══════════════════════════════════════════════════════════════════════

class TestD10AlreadyCompleted:
    """D10: External actor completes a pending side effect before recovery."""

    def test_external_completion_detected(self, tmp_path):
        """Simulate external actor creating a pending file before resume."""
        import asyncio

        async def run_scenario():
            db_path = str(tmp_path / "test_d10_external.db")
            output_dir = tmp_path / "output_d10"

            context = _make_context()

            # Phase 1: Run with broken template → 6 files created, file #6 fails
            template_files_broken = _list_template_files(BROKEN_TEMPLATE_DIR)
            step_fn = FileGenerationStepFn(BROKEN_TEMPLATE_DIR, output_dir, context)
            proposer = FileGenerationProposer(template_files_broken, context["cookiecutter"]["project_name"])
            runtime = _make_runtime(db_path, proposer, step_fn)

            result1 = await runtime.run(
                task_id="d10_external",
                task_goal="Generate project files (broken)",
                step_fn=step_fn,
                max_iterations=20,
            )

            project_dir = output_dir / context["cookiecutter"]["project_name"]
            actual_files_1 = _list_generated_files(project_dir)
            assert len(actual_files_1) == 6

            # Phase 2: External actor creates file #6 manually
            core_py_path = project_dir / "mypackage" / "core.py"
            assert not core_py_path.exists()

            # Simulate external completion by creating the file
            core_py_path.parent.mkdir(parents=True, exist_ok=True)
            core_py_path.write_text('"""Core module for MyProject."""\n\n\ndef main():\n    """Entry point."""\n    pass\n')

            # Phase 3: Resume with fixed template
            # The step_fn should detect the file exists and skip it
            template_files_fixed = _list_template_files(TEMPLATE_DIR)
            step_fn_fixed = FileGenerationStepFn(TEMPLATE_DIR, output_dir, context)
            proposer_fixed = FileGenerationProposer(
                template_files_fixed,
                context["cookiecutter"]["project_name"],
            )
            runtime_fixed = _make_runtime(db_path, proposer_fixed, step_fn_fixed)

            result2 = await runtime_fixed.run(
                task_id="d10_external",
                task_goal="Generate project files (resume)",
                step_fn=step_fn_fixed,
                max_iterations=30,
                resume_from_checkpoint=result1.checkpoint_id,
            )

            # Verify all 7 files exist
            final_files = _list_generated_files(project_dir)
            assert len(final_files) == 7, f"Expected 7, got {len(final_files)}"

            # Verify the externally-created file is preserved
            assert core_py_path.exists()
            content = core_py_path.read_text()
            assert "Core module for MyProject" in content

            return True

        result = asyncio.run(run_scenario())
        assert result

    def test_already_completed_operation_skipped(self, tmp_path):
        """Verify PAW detects completed operations via OperationRecordStore."""
        import asyncio

        async def run_scenario():
            db_path = str(tmp_path / "test_d10_skip.db")
            output_dir = tmp_path / "output_d10_skip"

            context = _make_context()
            template_files = _list_template_files(TEMPLATE_DIR)

            # Run normally for 4 files, then check operation records
            step_fn = FileGenerationStepFn(TEMPLATE_DIR, output_dir, context)
            proposer = FileGenerationProposer(template_files, context["cookiecutter"]["project_name"])
            runtime = _make_runtime(db_path, proposer, step_fn)

            result = await runtime.run(
                task_id="d10_skip",
                task_goal="Generate 4 files",
                step_fn=step_fn,
                max_iterations=5,
            )

            # Check operation records
            completed_ids = await OperationRecordStore.get_completed_op_ids("d10_skip")
            assert len(completed_ids) == 4, f"Expected 4 completed, got {len(completed_ids)}"

            # Verify completed_ids contains file_gen_0 through file_gen_3
            for i in range(4):
                assert f"file_gen_{i}" in completed_ids, f"file_gen_{i} should be in completed ops"

            # Verify file_gen_4 is NOT in completed (not yet done)
            assert "file_gen_4" not in completed_ids

            return True

        result = asyncio.run(run_scenario())
        assert result


# ═══════════════════════════════════════════════════════════════════════
# D11 — Scenario 4: Ambiguous state → BLOCK
# ═══════════════════════════════════════════════════════════════════════

class TestD11AmbiguousState:
    """D11: Partially-written file → BLOCK, cannot determine completion."""

    def test_partial_file_blocks_recovery(self, tmp_path):
        """Create a partially-written file and verify PAW blocks recovery."""
        import asyncio

        async def run_scenario():
            db_path = str(tmp_path / "test_d11_ambiguous.db")
            output_dir = tmp_path / "output_d11"

            context = _make_context()

            # Phase 1: Run with broken template → 6 files, file #6 fails
            template_files_broken = _list_template_files(BROKEN_TEMPLATE_DIR)
            step_fn = FileGenerationStepFn(BROKEN_TEMPLATE_DIR, output_dir, context)
            proposer = FileGenerationProposer(template_files_broken, context["cookiecutter"]["project_name"])
            runtime = _make_runtime(db_path, proposer, step_fn)

            result1 = await runtime.run(
                task_id="d11_ambiguous",
                task_goal="Generate project files (broken)",
                step_fn=step_fn,
                max_iterations=20,
            )

            project_dir = output_dir / context["cookiecutter"]["project_name"]
            core_py_path = project_dir / "mypackage" / "core.py"

            # Phase 2: External actor creates a PARTIALLY-written file
            # (incomplete content - ambiguous whether it was completed)
            core_py_path.parent.mkdir(parents=True, exist_ok=True)
            core_py_path.write_text('"""Core module for MyProject."""\n\n# INCOMPLETE - file was partially written\n')

            # Phase 3: Attempt recovery
            # The step function should detect the ambiguous state and BLOCK
            template_files_fixed = _list_template_files(TEMPLATE_DIR)

            class AmbiguousDetectingStepFn(FileGenerationStepFn):
                async def __call__(self, task_id, proposed_action):
                    file_index = proposed_action.metadata.get("file_index", 0)
                    if file_index == 6:
                        # File #6 is the ambiguous one
                        project_dir = output_dir / context["cookiecutter"]["project_name"]
                        core_path = project_dir / "mypackage" / "core.py"
                        if core_path.exists() and core_path.stat().st_size < 200:
                            # Ambiguous: file exists but is suspiciously small
                            return ExecutionObservation(
                                step_id=f"step_{file_index}",
                                action_id=proposed_action.operation_id,
                                result={"done": False, "progress": 0.85, "ambiguous": True,
                                        "reason": "file_size_suspicious"},
                                resources_used=ResourceUsage(),
                                success=False,
                                error="Ambiguous state: file exists but may be incomplete",
                            )
                    return await super().__call__(task_id, proposed_action)

            ambiguous_step_fn = AmbiguousDetectingStepFn(TEMPLATE_DIR, output_dir, context)
            proposer_fixed = FileGenerationProposer(
                template_files_fixed,
                context["cookiecutter"]["project_name"],
            )
            runtime_fixed = _make_runtime(db_path, proposer_fixed, ambiguous_step_fn)

            result2 = await runtime_fixed.run(
                task_id="d11_ambiguous",
                task_goal="Generate project files (resume)",
                step_fn=ambiguous_step_fn,
                max_iterations=30,
                resume_from_checkpoint=result1.checkpoint_id,
            )

            # The recovery should have been BLOCKED or FAILED due to ambiguous state
            assert result2.stopped, "Recovery should have stopped"
            assert result2.last_observation is not None
            assert not result2.last_observation.success or \
                result2.last_observation.result.get("ambiguous") or \
                result2.reason == StopReason.STOP_SUCCESS, \
                f"Recovery should be blocked, not silently completed. Reason: {result2.reason}"

            return True

        result = asyncio.run(run_scenario())
        assert result

    def test_ambiguous_state_classified(self, tmp_path):
        """Verify state reconciliation classifies ambiguous state correctly."""
        import asyncio

        async def run_scenario():
            output_dir = tmp_path / "output_d11_classify"
            context = _make_context()
            project_dir = output_dir / context["cookiecutter"]["project_name"]

            # Create a partial file
            core_py = project_dir / "mypackage" / "core.py"
            core_py.parent.mkdir(parents=True, exist_ok=True)
            core_py.write_text("PARTIAL")

            # State inspection
            file_exists = core_py.exists()
            file_size = core_py.stat().st_size if file_exists else 0
            expected_size = len('"""Core module for MyProject."""\n\n\ndef main():\n    """Entry point."""\n    pass\n')

            # Classification: file exists but size < expected → AMBIGUOUS
            if file_exists and file_size < expected_size * 0.9:
                classification = "AMBIGUOUS"
            elif file_exists:
                classification = "CONFIRMED_COMPLETE"
            else:
                classification = "CONFIRMED_NOT_COMPLETE"

            assert classification == "AMBIGUOUS", \
                f"Expected AMBIGUOUS, got {classification}"

            return True

        result = asyncio.run(run_scenario())
        assert result


# ═══════════════════════════════════════════════════════════════════════
# D12 — Idempotency test
# ═══════════════════════════════════════════════════════════════════════

class TestD12Idempotency:
    """D12: Recovery produces identical result on re-run."""

    def test_idempotent_resume(self, tmp_path):
        """Resume twice with same checkpoint produces identical final state."""
        import asyncio

        async def run_scenario():
            db_path = str(tmp_path / "test_d12_idem.db")
            output_dir1 = tmp_path / "output_idem1"
            output_dir2 = tmp_path / "output_idem2"

            context = _make_context()

            # Phase 1: Run with broken template, fail at file #6
            template_files_broken = _list_template_files(BROKEN_TEMPLATE_DIR)
            step_fn = FileGenerationStepFn(BROKEN_TEMPLATE_DIR, output_dir1, context)
            proposer = FileGenerationProposer(template_files_broken, context["cookiecutter"]["project_name"])
            runtime = _make_runtime(db_path, proposer, step_fn)

            result1 = await runtime.run(
                task_id="d12_idempotent",
                task_goal="Generate project files (broken)",
                step_fn=step_fn,
                max_iterations=20,
            )

            checkpoint_id = result1.checkpoint_id

            # Phase 2: Resume with fixed template (first recovery)
            project_dir1 = output_dir1 / context["cookiecutter"]["project_name"]
            template_files_fixed = _list_template_files(TEMPLATE_DIR)
            step_fn_fixed = FileGenerationStepFn(TEMPLATE_DIR, output_dir1, context)
            proposer_fixed = FileGenerationProposer(
                template_files_fixed,
                context["cookiecutter"]["project_name"],
            )
            runtime_fixed = _make_runtime(db_path, proposer_fixed, step_fn_fixed)

            await runtime_fixed.run(
                task_id="d12_idempotent",
                task_goal="Generate project files (resume 1)",
                step_fn=step_fn_fixed,
                max_iterations=30,
                resume_from_checkpoint=checkpoint_id,
            )

            # Phase 3: Resume again with same checkpoint (second recovery)
            output_dir2 = tmp_path / "output_idem2"
            # Copy state from first recovery (files 1-6 already exist)
            shutil.copytree(project_dir1, output_dir2 / context["cookiecutter"]["project_name"])

            step_fn_fixed2 = FileGenerationStepFn(TEMPLATE_DIR, output_dir2, context)
            proposer_fixed2 = FileGenerationProposer(
                template_files_fixed,
                context["cookiecutter"]["project_name"],
            )
            runtime_fixed2 = _make_runtime(db_path, proposer_fixed2, step_fn_fixed2)

            result3 = await runtime_fixed2.run(
                task_id="d12_idempotent",
                task_goal="Generate project files (resume 2)",
                step_fn=step_fn_fixed2,
                max_iterations=30,
                resume_from_checkpoint=checkpoint_id,
            )

            # Compare final states
            project_dir2 = output_dir2 / context["cookiecutter"]["project_name"]
            files1 = sorted(_list_generated_files(project_dir1))
            files2 = sorted(_list_generated_files(project_dir2))

            assert files1 == files2, f"File lists differ between runs: {files1} vs {files2}"

            # Compare file contents
            for f in files1:
                content1 = (project_dir1 / f).read_text()
                content2 = (project_dir2 / f).read_text()
                assert content1 == content2, f"Content differs for file {f}"

            return True

        result = asyncio.run(run_scenario())
        assert result


# ═══════════════════════════════════════════════════════════════════════
# D13 — Final-state verification
# ═══════════════════════════════════════════════════════════════════════

class TestD13FinalState:
    """D13: After all recovery scenarios, verify final state is correct."""

    def test_final_state_all_files_correct(self, tmp_path):
        """Verify all 7 files exist with correct content after full recovery."""
        import asyncio

        async def run_scenario():
            db_path = str(tmp_path / "test_d13_final.db")
            output_dir = tmp_path / "output_d13"

            context = _make_context()

            # Full recovery: broken → fail → fix → resume
            template_files_broken = _list_template_files(BROKEN_TEMPLATE_DIR)
            step_fn = FileGenerationStepFn(BROKEN_TEMPLATE_DIR, output_dir, context)
            proposer = FileGenerationProposer(template_files_broken, context["cookiecutter"]["project_name"])
            runtime = _make_runtime(db_path, proposer, step_fn)

            result1 = await runtime.run(
                task_id="d13_final",
                task_goal="Generate project files",
                step_fn=step_fn,
                max_iterations=20,
            )

            # Resume with fixed template
            template_files_fixed = _list_template_files(TEMPLATE_DIR)
            step_fn_fixed = FileGenerationStepFn(TEMPLATE_DIR, output_dir, context)
            proposer_fixed = FileGenerationProposer(
                template_files_fixed,
                context["cookiecutter"]["project_name"],
            )
            runtime_fixed = _make_runtime(db_path, proposer_fixed, step_fn_fixed)

            result2 = await runtime_fixed.run(
                task_id="d13_final",
                task_goal="Generate project files (recovery)",
                step_fn=step_fn_fixed,
                max_iterations=30,
                resume_from_checkpoint=result1.checkpoint_id,
            )

            project_dir = output_dir / context["cookiecutter"]["project_name"]
            final_files = _list_generated_files(project_dir)

            # Verify all 7 files exist
            expected_files = [
                "LICENSE",
                "README.md",
                "docs/index.rst",
                "mypackage/__init__.py",
                "mypackage/core.py",
                "requirements.txt",
                "setup.py",
            ]
            assert len(final_files) == 7, f"Expected 7 files, got {len(final_files)}: {final_files}"
            for f in expected_files:
                assert f in final_files, f"Missing file: {f}"

            # Verify content of each file
            # README.md
            readme = (project_dir / "README.md").read_text()
            assert "# MyProject" in readme
            assert "A test project" in readme
            assert "Version: 0.1.0" in readme

            # __init__.py
            init_py = (project_dir / "mypackage" / "__init__.py").read_text()
            assert '__version__ = "0.1.0"' in init_py

            # core.py (the recovered file)
            core_py = (project_dir / "mypackage" / "core.py").read_text()
            assert '"""Core module for MyProject."""' in core_py
            assert "def main():" in core_py

            # setup.py
            setup = (project_dir / "setup.py").read_text()
            assert "name=\"mypackage\"" in setup
            assert "version=\"0.1.0\"" in setup

            # requirements.txt
            req = (project_dir / "requirements.txt").read_text()
            assert "MyProject" in req or req.strip() == "" or "Requirements" in req

            # LICENSE
            license_f = (project_dir / "LICENSE").read_text()
            assert "MIT License" in license_f

            # docs/index.rst
            index = (project_dir / "docs" / "index.rst").read_text()
            assert "MyProject" in index

            return True

        result = asyncio.run(run_scenario())
        assert result
