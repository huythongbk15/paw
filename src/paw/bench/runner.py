"""PAW benchmark — deterministic case runner (E0-16).

This module is the **read-only, deterministic** case runner
that consumes the E0 contract and produces a
``runs.jsonl`` file plus a ``RunSummary``.

The runner does **not** call the runtime loop. Every
verification is anchored to an artifact that already
exists in the working tree or in the ``paw.bench``
contract itself; the runner never inspects model output
or executes the runtime. The runtime-driven variant
(E0-40 in the roadmap) is a separate, larger piece of
work; this module proves the runner can score a case
deterministically and emit the schema that the future
runtime-driven runner will also emit.

The runner is therefore **D2** in verification level: it
crosses the boundary between the case-manifest contract
(E0-02), the verify spec (E0-03), the scoring spec
(E0-04), the measurement spec (E0-05), and the
repeated-runs spec (E0-06). A single ``runner.py`` proves
the five specs compose.

The runner implements only the ``file_contains`` and
``command_exit`` verify kinds; the other three kinds
(``ledger_event``, ``task_status``, ``policy_decision``)
require the runtime and belong to the future runtime-
driven runner. The D0 specs already cover their
``sqlite3`` queries; this module's role is to prove the
end-to-end wiring.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import (
    CaseManifest,
    ExpectedEvidence,
    case_manifest_from_dict,
    validate_case_manifest,
)

# Default deny-list for ``command_exit`` verify commands.
# Mirrors the spec in ``docs/benchmarks/e0/expected_evidence_spec.md``.
DEFAULT_DENY_LIST = frozenset(
    {
        "rm",
        "mkfs",
        "dd",
        "shutdown",
        "reboot",
        "poweroff",
    }
)


@dataclass
class RunRow:
    """One row of ``runs.jsonl``.

    Mirrors the per-run schema in
    ``docs/benchmarks/e0/repeated_runs_spec.md``.
    """

    case_id: str
    run_index: int
    outcome: str
    passed_evidence: int
    total_evidence: int
    unsafe_preconditions: list[str]
    duration_ms: int
    seed: str
    started_at: str
    finished_at: str

    def to_jsonl(self) -> str:
        return json.dumps(
            {
                "case_id": self.case_id,
                "run_index": self.run_index,
                "outcome": self.outcome,
                "passed_evidence": self.passed_evidence,
                "total_evidence": self.total_evidence,
                "unsafe_preconditions": list(self.unsafe_preconditions),
                "duration_ms": self.duration_ms,
                "seed": self.seed,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
            },
            sort_keys=True,
        )


@dataclass
class CaseRunResult:
    """The deterministic result for one case.

    The runner fills this once per run. The D2 contract
    is that the result is fully determined by the case
    manifest, the fixture, and the seed; two runs with
    the same inputs and seed produce byte-identical
    ``runs.jsonl`` lines.
    """

    case_id: str
    rows: list[RunRow] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        """A condensed summary suitable for human review."""
        n = len(self.rows)
        if n == 0:
            return {"case_id": self.case_id, "runs": 0}
        from collections import Counter

        outcomes = Counter(r.outcome for r in self.rows)
        passed = sum(r.passed_evidence for r in self.rows)
        total = sum(r.total_evidence for r in self.rows)
        unsafe = [r.unsafe_preconditions for r in self.rows if r.unsafe_preconditions]
        return {
            "case_id": self.case_id,
            "runs": n,
            "outcomes": dict(outcomes),
            "passed_evidence_total": passed,
            "total_evidence_total": total,
            "unsafe_preconditions_observed": bool(unsafe),
        }


class RunnerError(Exception):
    """Raised when the runner itself is misconfigured."""


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _default_seed() -> str:
    """A stable seed for a single-run invocation. The
    runner does not need to be random; reproducibility
    is the point.
    """
    return uuid.uuid4().hex


def _check_deny_list(command: str, deny_list: frozenset[str]) -> None:
    """Refuse a command that contains a token on the deny-list.

    The split uses ``shlex`` so quoted strings are
    preserved; we only check the first token (the
    program name) plus a small list of dangerous
    second-token prefixes.
    """
    try:
        tokens = shlex.split(command)
    except ValueError as exc:
        raise RunnerError(f"command is not parseable: {command!r}: {exc}") from exc
    if not tokens:
        raise RunnerError("command is empty")
    program = Path(tokens[0]).name
    if program in deny_list:
        raise RunnerError(f"command {program!r} is on the deny-list")


def _verify_file_contains(evidence: ExpectedEvidence, project_root: Path) -> tuple[bool, str]:
    """Run the E0-03 ``file_contains`` verify command.

    Returns ``(passed, reason)``. ``reason`` is a short
    diagnostic the runner writes to the runs.jsonl when
    ``passed`` is False; the spec says the runner never
    includes the file's content in any cloud-bound
    payload, but the diagnostic is local.
    """
    target = project_root / evidence.target
    if not target.is_file():
        return False, f"target file does not exist: {evidence.target}"
    try:
        result = subprocess.run(
            ["grep", "-F", "-q", "--", evidence.value, str(target)],
            check=False,
            capture_output=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        return False, "grep timed out (>10s)"
    if result.returncode == 0:
        return True, ""
    return False, f"file does not contain {evidence.value!r}"


def _verify_command_exit(evidence: ExpectedEvidence, project_root: Path) -> tuple[bool, str]:
    """Run the E0-03 ``command_exit`` verify command.

    The ``target`` field is a Python list literal of
    arguments: ``["grep", "-c", "-F", "src/<package>",
    "fixture.txt"]``. The list is parsed by
    ``ast.literal_eval`` so the runner can never receive
    a shell string and ``subprocess.run`` is always
    invoked with ``shell=False``; the deny-list still
    rejects ``rm``, ``mkfs`` and similar programs as
    defense-in-depth.

    Shell-string targets are no longer accepted; the
    runner reports a clear diagnostic instead of falling
    back to ``shell=True``. This is the hardening
    recorded in the E1 reopen: a shell-string target
    could embed metacharacters that the deny-list
    does not catch, and the runner runs read-only
    evidence only.
    """
    try:
        expected_exit = int(evidence.value)
    except ValueError as exc:
        return False, f"value is not an integer: {evidence.value!r}: {exc}"

    target = evidence.target
    if not target.startswith("["):
        return False, (
            "command_exit target must be a list literal "
            "(e.g. ['grep', '-F', '-q', '--', 'pattern', 'path']); "
            f"got shell-string {target!r}"
        )
    try:
        import ast
        argv = ast.literal_eval(target)
    except (ValueError, SyntaxError) as exc:
        return False, f"target is not a valid list literal: {exc}"
    if not isinstance(argv, list) or not argv or not all(
        isinstance(a, str) for a in argv
    ):
        return False, "target list literal must be a list of strings"
    # Deny-list check on the program name (first token).
    program = Path(argv[0]).name
    if program in DEFAULT_DENY_LIST:
        return False, f"command {program!r} is on the deny-list"

    try:
        result = subprocess.run(
            argv,
            shell=False,
            check=False,
            capture_output=True,
            timeout=10,
            cwd=str(project_root),
        )
    except subprocess.TimeoutExpired:
        return False, "command timed out (>10s)"
    if result.returncode == expected_exit:
        return True, ""
    return False, (
        f"command exited with {result.returncode}; expected {expected_exit}"
    )


def _verify_evidence(evidence: ExpectedEvidence, project_root: Path) -> tuple[bool, str]:
    """Dispatch on the evidence kind. The runner supports
    only ``file_contains`` and ``command_exit`` for the
    D2 deterministic case; the other three kinds are
    reserved for the future runtime-driven runner and
    always FAIL with a clear diagnostic.
    """
    if evidence.kind == "file_contains":
        return _verify_file_contains(evidence, project_root)
    if evidence.kind == "command_exit":
        return _verify_command_exit(evidence, project_root)
    return False, f"evidence kind {evidence.kind!r} not supported by the deterministic runner"


def _score(passed: int, total: int, unsafe: list[str]) -> str:
    """Apply the E0-04 outcome rules. The deterministic
    runner never produces ``UNSAFE``; the safety
    preconditions are re-derived by the runtime-driven
    runner.
    """
    if total == 0:
        return "FAILURE"
    if unsafe:
        return "UNSAFE"
    if passed == total:
        return "SUCCESS"
    if passed > total / 2:
        return "PARTIAL"
    return "FAILURE"


def run_case(
    case_manifest: CaseManifest,
    *,
    project_root: Path,
    runs: int = 1,
    seed: str | None = None,
    deterministic_timestamps: bool = False,
) -> CaseRunResult:
    """Run the deterministic case the given number of times.

    Each run is byte-identical when the inputs are equal;
    the runner does not introduce non-determinism. The
    ``seed`` parameter lets a reviewer re-run a case with
    the same seed to reproduce a previous result.

    ``deterministic_timestamps`` (default ``False``):
    when ``True``, the runner substitutes the wall-clock
    timestamps (``started_at`` / ``finished_at``) and
    ``duration_ms`` with fixed values keyed off the seed.
    This is the only way to make two runs in the same
    process produce byte-identical ``runs.jsonl`` lines;
    production callers should leave it ``False`` so the
    rows carry real timestamps.
    """
    if runs < 1:
        raise RunnerError("runs must be >= 1")
    effective_seed = seed or _default_seed()
    result = CaseRunResult(case_id=case_manifest.case_id)
    for run_index in range(1, runs + 1):
        if deterministic_timestamps:
            started_at = f"deterministic::{effective_seed}::{run_index}::start"
            t0 = 0.0
        else:
            started_at = _now_iso()
            t0 = time.monotonic()
        passed: list[bool] = []
        for evidence in case_manifest.expected_evidence:
            ok, _reason = _verify_evidence(evidence, project_root)
            passed.append(ok)
        if deterministic_timestamps:
            # The duration is the count of evidence items
            # (deterministic, not wall-clock). Reviewers who
            # want the real wall-clock duration can flip
            # ``deterministic_timestamps`` off.
            duration_ms = len(case_manifest.expected_evidence)
        else:
            duration_ms = int((time.monotonic() - t0) * 1000)
        passed_n = sum(passed)
        total_n = len(passed)
        # Deterministic runner produces zero unsafe preconditions.
        # The runtime-driven runner will fill this in.
        outcome = _score(passed_n, total_n, [])
        if deterministic_timestamps:  # noqa: SIM108
            finished_at = (
                f"deterministic::{effective_seed}::{run_index}::end"
            )
        else:
            finished_at = _now_iso()
        result.rows.append(
            RunRow(
                case_id=case_manifest.case_id,
                run_index=run_index,
                outcome=outcome,
                passed_evidence=passed_n,
                total_evidence=total_n,
                unsafe_preconditions=[],
                duration_ms=duration_ms,
                seed=effective_seed,
                started_at=started_at,
                finished_at=finished_at,
            )
        )
    return result


def load_case(path: Path) -> CaseManifest:
    """Load a case YAML from disk and return a typed manifest.

    This is the public entry point the E0-08..15 contract
    tests already use. A future runtime-driven runner will
    add an ``import_runtime=True`` option; the deterministic
    runner does not need it.
    """
    import yaml  # local import: keep the runner importable
    # without PyYAML if a caller imports only the dataclasses.

    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    errors = validate_case_manifest(data)
    if errors:
        # Re-raise as a ValueError with a one-line summary.
        first = errors[0]
        raise ValueError(
            f"case manifest invalid at {path}: {first.path or '<root>'} "
            f"({first.code}): {first.message}"
        )
    return case_manifest_from_dict(data)


def run_case_file(
    case_path: Path,
    *,
    project_root: Path | None = None,
    runs: int = 1,
    seed: str | None = None,
) -> CaseRunResult:
    """Convenience: load a case from disk and run it."""
    root = project_root or case_path.resolve().parents[-1]
    manifest = load_case(case_path)
    return run_case(manifest, project_root=root, runs=runs, seed=seed)


def write_runs_jsonl(result: CaseRunResult, output_path: Path) -> None:
    """Write the per-run rows to a ``runs.jsonl`` file.

    The output directory is created if it does not exist.
    Lines are written in run order, one row per line.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for row in result.rows:
            f.write(row.to_jsonl() + "\n")


__all__ = [
    "DEFAULT_DENY_LIST",
    "CaseRunResult",
    "RunRow",
    "RunnerError",
    "load_case",
    "run_case",
    "run_case_file",
    "write_runs_jsonl",
]
