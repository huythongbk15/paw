"""PAW benchmark — versioned case manifest contract (E0-02).

This module is the canonical owner of the E0 benchmark case
manifest schema. It is a read-only contract used by the future
E0-16 runner; the PAW core runtime never imports this module.

Design constraints (from E0-01 decision record):

1. **No second result model.** A case manifest is a plain
   dataclass; it does not introduce a ``BenchmarkTask`` or
   ``BenchmarkResult`` that would compete with the existing
   ``paw.core.task.Task`` and ``paw.core.models.TaskResult``.

2. **Cases are filesystem YAML, not SQLite.** The runtime
   keeps its single persistence owner (SQLite via
   ``paw.core.storage``); benchmark cases live under
   ``benchmarks/e0/cases/<case_id>.yaml`` in the working
   tree, versioned alongside source.

3. **Every manifest is versioned.** The ``schema_version``
   field lets future schema changes fail closed: a manifest
   with an unknown version is rejected by ``load_case``.

4. **Fixture revision is explicit.** Every fixture path is
   paired with a ``revision`` (git SHA or "dirty") so a
   reviewer can tell whether the fixture changed since the
   case was authored.

5. **Privacy class is mandatory.** The ``privacy_class``
   field is required and may not be empty. This protects
   against accidentally sending a marked source to a
   cloud provider in a future E2 escalation step.

This module owns the *contract* only. There is no I/O here:
the future E0-16 runner will import ``load_case`` to parse
a YAML file, then re-emit the trace through the canonical
runtime loop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, ClassVar

# Schema version of the case manifest itself. Bump when the
# dataclass fields change. ``load_case`` rejects any manifest
# whose ``schema_version`` does not match the current value.
CASE_MANIFEST_SCHEMA_VERSION = "1.0.0"


class PrivacyClass(StrEnum):
    """Where a case's source may be sent.

    The values are ordered from least to most restricted so
    that ``PrivacyClass`` can be used as a key in
    benchmark-level rules (``min_privacy``).
    """

    PUBLIC = "public"             # May be sent to any provider.
    INTERNAL = "internal"         # May be sent to approved cloud.
    WORKSPACE = "workspace"        # Workspace only; no remote.
    SECRET = "secret"             # Never sent off-box.

    @classmethod
    def parse(cls, raw: str) -> PrivacyClass:
        """Strict parse: unknown values raise ``ValueError``."""
        try:
            return cls(raw)
        except ValueError as exc:
            raise ValueError(
                f"unknown privacy class: {raw!r}; "
                f"expected one of {[p.value for p in cls]}"
            ) from exc


class CaseCategory(StrEnum):
    """The minimum case set defined in ``EXECUTION_CHECKLIST.md`` E0-08..15."""

    REPO_UNDERSTANDING = "repo_understanding"
    DEFECT_LOCALIZATION = "defect_localization"
    CROSS_MODULE_CHANGE = "cross_module_change"
    REFACTORING = "refactoring"
    ARCHITECTURE_DECISION = "architecture_decision"
    INTERRUPTED_RECOVERY = "interrupted_recovery"
    PRIVACY_NEGATIVE = "privacy_negative"
    INSUFFICIENT_CONTEXT = "insufficient_context"

    @classmethod
    def parse(cls, raw: str) -> CaseCategory:
        try:
            return cls(raw)
        except ValueError as exc:
            raise ValueError(
                f"unknown case category: {raw!r}; "
                f"expected one of {[c.value for c in cls]}"
            ) from exc


@dataclass
class FixtureRef:
    """A single fixture file referenced by a case.

    Attributes:
        path: Repository-relative path to the fixture file
            (e.g. ``benchmarks/e0/fixtures/pa_small_repo.txt``).
        revision: Git SHA, branch, or ``"dirty"`` indicating
            the source revision this fixture was authored
            against. The future E0-16 runner must verify that
            the on-disk fixture hash matches this revision
            before running the case.
        purpose: Short human-readable reason this fixture
            exists (e.g. ``"input repository"``).
    """

    path: str
    revision: str
    purpose: str = ""

    def __post_init__(self) -> None:
        if not self.path:
            raise ValueError("FixtureRef.path must not be empty")
        if not self.revision:
            raise ValueError("FixtureRef.revision must not be empty")
        if self.path.startswith("/"):
            raise ValueError(
                f"FixtureRef.path must be repository-relative: {self.path!r}"
            )


@dataclass
class ExpectedEvidence:
    """Reviewed expected evidence for a case.

    Attributes:
            kind: One of ``"file_contains"``, ``"command_exit"``,
                ``"ledger_event"``, ``"task_status"``,
                ``"policy_decision"``. Future runner versions
                may add new kinds.
            target: Where the evidence is expected. For
                ``"file_contains"``, the repository-relative
                file path. For ``"ledger_event"``,
                ``"policy_decision"`` and ``"task_status"``,
                the value to match on the appropriate ledger
                field.
            value: The matched string. Interpretation depends
                on ``kind``; for ``"command_exit"`` it is the
                integer exit code as a string.
            reviewer: Human-readable reviewer tag (e.g. a
                git handle) that the runner will cite when
                reporting. Cases without a reviewer cannot
                be promoted to ``VERIFIED``.
    """

    kind: str
    target: str
    value: str
    reviewer: str = ""

    ALLOWED_KINDS: ClassVar[set[str]] = {
        "file_contains",
        "command_exit",
        "ledger_event",
        "task_status",
        "policy_decision",
    }

    def __post_init__(self) -> None:
        if self.kind not in self.ALLOWED_KINDS:
            raise ValueError(
                f"ExpectedEvidence.kind must be one of "
                f"{sorted(self.ALLOWED_KINDS)}; got {self.kind!r}"
            )
        if not self.target:
            raise ValueError("ExpectedEvidence.target must not be empty")
        # ``value`` is intentionally allowed to be empty
        # (e.g. for ``"ledger_event"`` with kind=present-only).


@dataclass
class CaseManifest:
    """The E0 case manifest contract.

    Attributes:
            case_id: Stable, globally-unique identifier. Must
                match the YAML filename
                (``benchmarks/e0/cases/<case_id>.yaml``).
            schema_version: The schema version this manifest
                was authored against. Must equal
                ``CASE_MANIFEST_SCHEMA_VERSION``; otherwise
                ``load_case`` rejects the file.
            category: One of ``CaseCategory``. The future
                runner uses this to pick the appropriate
                scoring rule.
            privacy_class: One of ``PrivacyClass``. The
                future E2 escalation step must honor this
                when deciding whether to send a remote
                provider.
            goal: The user-visible goal the case tests.
                Mirrors the ``Task.goal`` field so the
                runner can drive the runtime directly.
            fixtures: The fixture files this case needs.
                At least one is required.
            expected_evidence: Reviewed expected outcomes.
                At least one is required; the case cannot
                be promoted to ``VERIFIED`` without a
                reviewer on every entry.
            timeout_seconds: Hard wall-clock budget. The
                runner aborts the case if it is exceeded.
            max_iterations: Hard iteration budget. Mirrors
                ``AutonomyBudget.max_iterations``.
            tags: Free-form labels (e.g. ``["smoke",
                "registry"]``) used by the runner to
                filter or group cases.
    """

    case_id: str
    schema_version: str
    category: CaseCategory
    privacy_class: PrivacyClass
    goal: str
    fixtures: list[FixtureRef] = field(default_factory=list)
    expected_evidence: list[ExpectedEvidence] = field(default_factory=list)
    timeout_seconds: int = 300
    max_iterations: int = 20
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.case_id:
            raise ValueError("CaseManifest.case_id must not be empty")
        if "/" in self.case_id or "\\" in self.case_id:
            raise ValueError(
                f"CaseManifest.case_id must not contain path separators: "
                f"{self.case_id!r}"
            )
        if self.schema_version != CASE_MANIFEST_SCHEMA_VERSION:
            raise ValueError(
                f"CaseManifest.schema_version must equal "
                f"{CASE_MANIFEST_SCHEMA_VERSION!r}; got {self.schema_version!r}"
            )
        if not self.goal:
            raise ValueError("CaseManifest.goal must not be empty")
        if not self.fixtures:
            raise ValueError("CaseManifest.fixtures must not be empty")
        if not self.expected_evidence:
            raise ValueError(
                "CaseManifest.expected_evidence must not be empty "
                "(a case without expected evidence cannot be VERIFIED)"
            )
        for ev in self.expected_evidence:
            if not ev.reviewer:
                raise ValueError(
                    f"expected_evidence entry {ev.kind!r} has no reviewer; "
                    f"every case must carry a reviewed outcome"
                )
        if self.timeout_seconds <= 0:
            raise ValueError("CaseManifest.timeout_seconds must be positive")
        if self.max_iterations <= 0:
            raise ValueError("CaseManifest.max_iterations must be positive")


def case_manifest_from_dict(data: dict[str, Any]) -> CaseManifest:
    """Parse a raw dict (e.g. from ``yaml.safe_load``) into a CaseManifest.

    This function is the single boundary between the YAML
    representation and the typed contract. It is the only
    function the future E0-16 runner will import to load
    cases; everything else in this module is internal.
    """
    if not isinstance(data, dict):
        raise TypeError(
            f"case manifest must be a mapping; got {type(data).__name__}"
        )
    fixtures = [
        FixtureRef(**f) if isinstance(f, dict) else f
        for f in data.get("fixtures", [])
    ]
    evidence = [
        ExpectedEvidence(**e) if isinstance(e, dict) else e
        for e in data.get("expected_evidence", [])
    ]
    return CaseManifest(
        case_id=str(data["case_id"]),
        schema_version=str(data.get("schema_version", "")),
        category=CaseCategory.parse(str(data["category"])),
        privacy_class=PrivacyClass.parse(str(data["privacy_class"])),
        goal=str(data["goal"]),
        fixtures=fixtures,
        expected_evidence=evidence,
        timeout_seconds=int(data.get("timeout_seconds", 300)),
        max_iterations=int(data.get("max_iterations", 20)),
        tags=list(data.get("tags", [])),
    )


def case_manifest_to_dict(m: CaseManifest) -> dict[str, Any]:
    """Serialize a CaseManifest to a JSON/YAML-friendly dict."""
    return {
        "schema_version": m.schema_version,
        "case_id": m.case_id,
        "category": m.category.value,
        "privacy_class": m.privacy_class.value,
        "goal": m.goal,
        "fixtures": [
            {"path": f.path, "revision": f.revision, "purpose": f.purpose}
            for f in m.fixtures
        ],
        "expected_evidence": [
            {"kind": e.kind, "target": e.target, "value": e.value, "reviewer": e.reviewer}
            for e in m.expected_evidence
        ],
        "timeout_seconds": m.timeout_seconds,
        "max_iterations": m.max_iterations,
        "tags": list(m.tags),
    }


class SchemaError:
    """A single schema-validation error.

    Attributes:
        path: Dot-separated JSON-pointer-ish path to the
            offending field (e.g. ``"fixtures.0.path"``).
        code: Short stable identifier the runner can
            match on (e.g. ``"missing_field"``,
            ``"unknown_enum"``, ``"empty_string"``).
        message: Human-readable explanation.
    """

    def __init__(self, path: str, code: str, message: str) -> None:
        self.path = path
        self.code = code
        self.message = message

    def __repr__(self) -> str:
        return f"SchemaError({self.path!r}, {self.code!r}, {self.message!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SchemaError):
            return NotImplemented
        return (
            self.path == other.path
            and self.code == other.code
            and self.message == other.message
        )

    def __hash__(self) -> int:
        return hash((self.path, self.code, self.message))


def validate_case_manifest(data: Any) -> list[SchemaError]:
    """Validate a raw dict (e.g. from ``yaml.safe_load``).

    Returns a list of ``SchemaError`` (empty if valid).
    Does not raise. This is the E0-07 contract: a
    malformed or incomplete case manifest is reported
    with a stable error code, never silently fixed.

    The function is the single boundary between the YAML
    representation and the typed contract. The runner
    imports it; it never imports the dataclass directly
    (the dataclass's ``__post_init__`` raises on the
    first error, which is the wrong shape for "report
    every problem at once").
    """
    errors: list[SchemaError] = []

    def add(path: str, code: str, message: str) -> None:
        errors.append(SchemaError(path, code, message))

    if not isinstance(data, dict):
        add(
            "",
            "type_error",
            f"case manifest must be a mapping; got {type(data).__name__}",
        )
        return errors

    # Required string fields.
    for fname in ("case_id", "schema_version", "goal"):
        if fname not in data:
            add(fname, "missing_field", f"required field {fname!r} is missing")
            continue
        value = data[fname]
        if not isinstance(value, str):
            add(
                fname,
                "type_error",
                f"{fname!r} must be a string; got {type(value).__name__}",
            )
            continue
        if not value:
            add(fname, "empty_string", f"{fname!r} must not be empty")

    # schema_version must match the current contract.
    sv = data.get("schema_version", "")
    if sv == CASE_MANIFEST_SCHEMA_VERSION:
        pass
    elif not sv:
        # Already reported as missing_field/empty_string above.
        pass
    else:
        add(
            "schema_version",
            "version_mismatch",
            f"schema_version must equal {CASE_MANIFEST_SCHEMA_VERSION!r}; got {sv!r}",
        )

    # case_id must not contain path separators.
    case_id = data.get("case_id", "")
    if isinstance(case_id, str) and case_id and ("/" in case_id or "\\" in case_id):
        add(
            "case_id",
            "invalid_characters",
            f"case_id must not contain path separators; got {case_id!r}",
        )

    # category must be a known CaseCategory.
    cat = data.get("category", "")
    if cat not in {c.value for c in CaseCategory}:
        add(
            "category",
            "unknown_enum",
            f"category must be one of {[c.value for c in CaseCategory]}; got {cat!r}",
        )

    # privacy_class must be a known PrivacyClass.
    pc = data.get("privacy_class", "")
    if pc not in {p.value for p in PrivacyClass}:
        add(
            "privacy_class",
            "unknown_enum",
            f"privacy_class must be one of {[p.value for p in PrivacyClass]}; got {pc!r}",
        )

    # fixtures: non-empty list of {path, revision, purpose?}.
    fixtures = data.get("fixtures", None)
    if fixtures is None:
        add("fixtures", "missing_field", "required field 'fixtures' is missing")
    elif not isinstance(fixtures, list):
        add(
            "fixtures",
            "type_error",
            f"fixtures must be a list; got {type(fixtures).__name__}",
        )
    elif not fixtures:
        add("fixtures", "empty_list", "fixtures must not be empty")
    else:
        for i, f in enumerate(fixtures):
            fpath = f"fixtures.{i}"
            if not isinstance(f, dict):
                add(
                    fpath,
                    "type_error",
                    f"fixture entry must be a mapping; got {type(f).__name__}",
                )
                continue
            for sub in ("path", "revision"):
                if sub not in f:
                    add(
                        f"{fpath}.{sub}",
                        "missing_field",
                        f"fixture requires {sub!r}",
                    )
                    continue
                v = f[sub]
                if not isinstance(v, str):
                    add(
                        f"{fpath}.{sub}",
                        "type_error",
                        f"fixture.{sub} must be a string; got {type(v).__name__}",
                    )
                    continue
                if not v:
                    add(
                        f"{fpath}.{sub}",
                        "empty_string",
                        f"fixture.{sub} must not be empty",
                    )
            # path must be repo-relative.
            fpath_val = f.get("path", "")
            if isinstance(fpath_val, str) and fpath_val.startswith("/"):
                add(
                    f"{fpath}.path",
                    "absolute_path",
                    f"fixture.path must be repository-relative; got {fpath_val!r}",
                )

    # expected_evidence: non-empty list, every entry has
    # kind in ALLOWED_KINDS, target non-empty, reviewer
    # non-empty.
    evidence = data.get("expected_evidence", None)
    if evidence is None:
        add(
            "expected_evidence",
            "missing_field",
            "required field 'expected_evidence' is missing",
        )
    elif not isinstance(evidence, list):
        add(
            "expected_evidence",
            "type_error",
            f"expected_evidence must be a list; got {type(evidence).__name__}",
        )
    elif not evidence:
        add(
            "expected_evidence",
            "empty_list",
            "expected_evidence must not be empty",
        )
    else:
        for i, e in enumerate(evidence):
            epath = f"expected_evidence.{i}"
            if not isinstance(e, dict):
                add(
                    epath,
                    "type_error",
                    f"expected_evidence entry must be a mapping; got {type(e).__name__}",
                )
                continue
            kind = e.get("kind", "")
            allowed = {
                "file_contains",
                "command_exit",
                "ledger_event",
                "task_status",
                "policy_decision",
            }
            if kind not in allowed:
                add(
                    f"{epath}.kind",
                    "unknown_enum",
                    f"kind must be one of {sorted(allowed)}; got {kind!r}",
                )
            target = e.get("target", "")
            if not isinstance(target, str):
                add(
                    f"{epath}.target",
                    "type_error",
                    f"target must be a string; got {type(target).__name__}",
                )
            elif not target:
                add(
                    f"{epath}.target",
                    "empty_string",
                    "target must not be empty",
                )
            reviewer = e.get("reviewer", "")
            if "reviewer" not in e:
                add(
                    f"{epath}.reviewer",
                    "missing_field",
                    "every expected_evidence entry requires a reviewer",
                )
            elif not isinstance(reviewer, str):
                add(
                    f"{epath}.reviewer",
                    "type_error",
                    f"reviewer must be a string; got {type(reviewer).__name__}",
                )
            elif not reviewer:
                add(
                    f"{epath}.reviewer",
                    "empty_string",
                    "reviewer must not be empty",
                )

    # Budget fields.
    for fname, _default in (("timeout_seconds", 300), ("max_iterations", 20)):
        if fname not in data:
            continue  # Optional; default will be used.
        v = data[fname]
        if not isinstance(v, int) or isinstance(v, bool):
            add(
                fname,
                "type_error",
                f"{fname} must be an integer; got {type(v).__name__}",
            )
            continue
        if v <= 0:
            add(
                fname,
                "out_of_range",
                f"{fname} must be positive; got {v}",
            )

    return errors


def is_valid_case_manifest(data: Any) -> bool:
    """Convenience: ``validate_case_manifest(data) == []``."""
    return len(validate_case_manifest(data)) == 0


__all__ = [
    "CASE_MANIFEST_SCHEMA_VERSION",
    "CaseCategory",
    "CaseManifest",
    "ExpectedEvidence",
    "FixtureRef",
    "PrivacyClass",
    "SchemaError",
    "case_manifest_from_dict",
    "case_manifest_to_dict",
    "is_valid_case_manifest",
    "validate_case_manifest",
]
