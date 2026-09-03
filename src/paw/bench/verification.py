"""PAW benchmark — verification artifact (E0-39).

This module is the canonical owner of the
``VerificationSpec`` and ``VerificationRecord`` types
declared in the E0 architecture (Layer 2 of
``verification_layers_spec.md``). The two types are
the contract between a case's accepted
``expected_evidence`` and the runner's score; they are
**not** a new result model and they do not replace
``paw.core.models.TaskResult``.

Key design rules (from
``docs/benchmarks/e0/verification_layers_spec.md``):

1. ``VerificationSpec`` describes an acceptance check
   the runner will perform. It carries the spec id,
   version, the check kind, the expected outcome, the
   capability / privacy requirements, the timeout, and
   the evidence / artifact paths the runner should
   consult.
2. ``VerificationRecord`` is the runner's result of one
   ``VerificationSpec``. It carries the spec reference,
   the result enum (``PASS`` / ``FAIL`` / ``ERROR`` /
   ``SKIPPED``), the observed outcome, observed output,
   the verifier identity, and the timestamps.
3. A ``SKIPPED`` record is **never** silently
   successful. A skipped check is reported as skipped;
   the runner may not promote a skipped record to
   ``PASS``.
4. The record is anchored to a ``task_id`` and a
   ``project_revision``; this is what makes the
   verified trace reproducible across runs.

These types are E0-39 deliverables; the E0-16 runner
does not consume them yet (the deterministic runner
only scores ``file_contains`` and ``command_exit``
evidence via direct file / subprocess work). They are
the future runtime-driven runner's contract.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class VerificationResult(StrEnum):
    """The four possible outcomes of a single
    ``VerificationSpec`` execution.

    The order matters: ``SKIPPED`` is the lowest
    (never promoted); ``ERROR`` means the check itself
    failed (the runner could not run it); ``PASS`` and
    ``FAIL`` are the two real outcomes the benchmark
    tracks.
    """

    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"

    @classmethod
    def parse(cls, raw: str) -> VerificationResult:
        try:
            return cls(raw)
        except ValueError as exc:
            raise ValueError(
                f"unknown verification result: {raw!r}; "
                f"expected one of {[r.value for r in cls]}"
            ) from exc


@dataclass
class VerificationSpec:
    """A single acceptance check a case must pass.

    Attributes:
            spec_id: Stable, globally-unique identifier
                (e.g. ``"small_repo_understand_blocked"``).
            spec_version: Semantic version of the spec
                (e.g. ``"1.0.0"``).
            task_id: The Task whose verification this is.
            project_revision: The project revision the
                spec was authored against.
            check_kind: One of the runner-supported verify
                kinds (``file_contains``, ``command_exit``,
                ``ledger_event``, ``task_status``,
                ``policy_decision``).
            expected_outcome: The literal the runner must
                match (e.g. ``"BLOCKED"`` for a
                ``task_status`` check).
            capability_requirements: Capabilities the
                runner must hold to perform the check
                (e.g. ``["FILESYSTEM_READ"]`` for a
                ``file_contains`` check).
            privacy_requirements: Privacy class the
                runner must respect (``workspace``,
                ``internal``, ``public``, ``secret``).
            timeout_seconds: Wall-clock cap on the check.
            evidence_paths: Files the runner reads to
                perform the check.
            artifact_paths: Files the runner writes as
                side effects of the check (rare; usually
                empty).
    """

    spec_id: str
    spec_version: str
    task_id: str
    project_revision: str
    check_kind: str
    expected_outcome: str
    capability_requirements: list[str] = field(default_factory=list)
    privacy_requirements: str = "workspace"
    timeout_seconds: int = 60
    evidence_paths: list[str] = field(default_factory=list)
    artifact_paths: list[str] = field(default_factory=list)

    ALLOWED_KINDS: frozenset[str] = frozenset(
        {
            "file_contains",
            "command_exit",
            "ledger_event",
            "task_status",
            "policy_decision",
        }
    )

    def __post_init__(self) -> None:
        if not self.spec_id:
            raise ValueError("VerificationSpec.spec_id must not be empty")
        if "." not in self.spec_version:
            raise ValueError(
                f"VerificationSpec.spec_version must be a semantic "
                f"version: got {self.spec_version!r}"
            )
        if not self.task_id:
            raise ValueError("VerificationSpec.task_id must not be empty")
        if not self.project_revision:
            raise ValueError(
                "VerificationSpec.project_revision must not be empty"
            )
        if self.check_kind not in self.ALLOWED_KINDS:
            raise ValueError(
                f"VerificationSpec.check_kind must be one of "
                f"{sorted(self.ALLOWED_KINDS)}; got {self.check_kind!r}"
            )
        if self.timeout_seconds <= 0:
            raise ValueError(
                f"VerificationSpec.timeout_seconds must be "
                f"positive; got {self.timeout_seconds}"
            )


@dataclass
class VerificationRecord:
    """The runner's record of one ``VerificationSpec``.

    Attributes:
            spec: Reference to the spec the record
                answers. Stored as a structured value
                (not just the spec id) so a reviewer can
                cross-check without an external lookup.
            result: The outcome enum.
            observed_outcome: The literal the runner
                actually saw.
            observed_output: Free-form text the runner
                captured (the literal command output, the
                file content snippet, etc.).
            error: None on PASS/FAIL/SKIPPED; a typed
                error message on ERROR.
            verifier_identity: The runner or human who
                ran the check.
            started_at: ISO-8601 timestamp (UTC).
            finished_at: ISO-8601 timestamp (UTC).
            provenance: The path of the spec in the source
                tree (e.g. ``"src/paw/bench/verification.py"``).
    """

    spec: VerificationSpec
    result: VerificationResult
    observed_outcome: str = ""
    observed_output: str = ""
    error: str | None = None
    verifier_identity: str = "paw.bench.deterministic_runner"
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    finished_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    provenance: str = "src/paw/bench/verification.py"

    def __post_init__(self) -> None:
        if self.error is not None and self.result is not VerificationResult.ERROR:
            raise ValueError(
                f"VerificationRecord.error must be None when result is "
                f"{self.result.value!r}; got error={self.error!r}"
            )

    def is_pass(self) -> bool:
        """``SKIPPED`` is never ``PASS`` (the E0-38 rule)."""
        return self.result is VerificationResult.PASS

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec": {
                "spec_id": self.spec.spec_id,
                "spec_version": self.spec.spec_version,
                "task_id": self.spec.task_id,
                "project_revision": self.spec.project_revision,
                "check_kind": self.spec.check_kind,
                "expected_outcome": self.spec.expected_outcome,
                "capability_requirements": list(
                    self.spec.capability_requirements
                ),
                "privacy_requirements": self.spec.privacy_requirements,
                "timeout_seconds": self.spec.timeout_seconds,
                "evidence_paths": list(self.spec.evidence_paths),
                "artifact_paths": list(self.spec.artifact_paths),
            },
            "result": self.result.value,
            "observed_outcome": self.observed_outcome,
            "observed_output": self.observed_output,
            "error": self.error,
            "verifier_identity": self.verifier_identity,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "provenance": self.provenance,
        }

    def to_jsonl(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)


def make_spec_from_evidence(
    *,
    spec_id: str,
    case_id: str,
    project_revision: str,
    kind: str,
    target: str,
    expected_value: str,
) -> VerificationSpec:
    """Build a ``VerificationSpec`` from a single
    ``ExpectedEvidence`` entry. This is the helper the
    future runtime-driven runner uses to convert the
    E0-02 manifest contract into per-evidence specs
    the runner then evaluates.
    """
    return VerificationSpec(
        spec_id=spec_id,
        spec_version="1.0.0",
        task_id=case_id,
        project_revision=project_revision,
        check_kind=kind,
        expected_outcome=expected_value,
        evidence_paths=[target] if target else [],
        capability_requirements=(
            ["FILESYSTEM_READ"] if kind == "file_contains" else []
        ),
    )


__all__ = [
    "VerificationRecord",
    "VerificationResult",
    "VerificationSpec",
    "make_spec_from_evidence",
]
