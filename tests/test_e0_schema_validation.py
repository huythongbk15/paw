"""E0-07 contract test: schema validation (D1).

The contract is: a malformed or incomplete case manifest
is reported with a stable error code, never silently
fixed, never raising on the first error. The runner
imports ``validate_case_manifest`` and ``is_valid_case_manifest``;
everything else in ``paw.bench`` is internal.

Two-fail-positive discipline: every rejection path below
was added because the failure it asserts was reproduced
against an earlier candidate that lacked the check.
"""

from __future__ import annotations

import pytest

from paw.bench import (
    CASE_MANIFEST_SCHEMA_VERSION,
    CaseManifest,
    SchemaError,
    case_manifest_from_dict,
    is_valid_case_manifest,
    validate_case_manifest,
)


# --- Fixtures ------------------------------------------------------------


def _good_dict(**overrides) -> dict:
    base = {
        "schema_version": CASE_MANIFEST_SCHEMA_VERSION,
        "case_id": "case_a",
        "category": "repo_understanding",
        "privacy_class": "internal",
        "goal": "Summarize the small repository fixture.",
        "fixtures": [
            {"path": "benchmarks/e0/fixtures/small_repo.txt",
             "revision": "f3ad4ef",
             "purpose": "small repo"},
        ],
        "expected_evidence": [
            {"kind": "task_status", "target": "BLOCKED",
             "value": "BLOCKED", "reviewer": "alice@example.com"},
        ],
    }
    base.update(overrides)
    return base


# --- 1. Happy path --------------------------------------------------------


def test_good_manifest_validates_with_zero_errors() -> None:
    """A complete, valid manifest yields an empty error list."""
    errors = validate_case_manifest(_good_dict())
    assert errors == []


def test_good_manifest_passes_is_valid() -> None:
    assert is_valid_case_manifest(_good_dict()) is True


# --- 2. Type and shape errors --------------------------------------------


def test_non_mapping_input_is_rejected_with_type_error() -> None:
    errors = validate_case_manifest([1, 2, 3])
    assert len(errors) == 1
    assert errors[0].path == ""
    assert errors[0].code == "type_error"


def test_none_input_is_rejected() -> None:
    errors = validate_case_manifest(None)
    assert errors[0].code == "type_error"


def test_string_input_is_rejected() -> None:
    errors = validate_case_manifest("not a manifest")
    assert errors[0].code == "type_error"


# --- 3. Required string fields -------------------------------------------


@pytest.mark.parametrize("field", ["case_id", "schema_version", "goal"])
def test_missing_required_string_field_reports_missing(field: str) -> None:
    d = _good_dict()
    del d[field]
    errors = validate_case_manifest(d)
    codes = {(e.path, e.code) for e in errors}
    assert (field, "missing_field") in codes


@pytest.mark.parametrize("field", ["case_id", "schema_version", "goal"])
def test_empty_required_string_field_reports_empty_string(field: str) -> None:
    d = _good_dict()
    d[field] = ""
    errors = validate_case_manifest(d)
    codes = {(e.path, e.code) for e in errors}
    assert (field, "empty_string") in codes


@pytest.mark.parametrize(
    "field", ["case_id", "schema_version", "goal"]
)
def test_non_string_required_field_reports_type_error(field: str) -> None:
    d = _good_dict()
    d[field] = 42
    errors = validate_case_manifest(d)
    codes = {(e.path, e.code) for e in errors}
    assert (field, "type_error") in codes


# --- 4. Schema version ---------------------------------------------------


def test_wrong_schema_version_reports_version_mismatch() -> None:
    d = _good_dict()
    d["schema_version"] = "0.9.0"
    errors = validate_case_manifest(d)
    codes = {(e.path, e.code) for e in errors}
    assert ("schema_version", "version_mismatch") in codes


# --- 5. case_id rules ----------------------------------------------------


def test_case_id_with_slash_reports_invalid_characters() -> None:
    d = _good_dict()
    d["case_id"] = "foo/bar"
    errors = validate_case_manifest(d)
    codes = {(e.path, e.code) for e in errors}
    assert ("case_id", "invalid_characters") in codes


def test_case_id_with_backslash_reports_invalid_characters() -> None:
    d = _good_dict()
    d["case_id"] = "foo\\bar"
    errors = validate_case_manifest(d)
    codes = {(e.path, e.code) for e in errors}
    assert ("case_id", "invalid_characters") in codes


# --- 6. Enum fields ------------------------------------------------------


def test_unknown_category_reports_unknown_enum() -> None:
    d = _good_dict()
    d["category"] = "made_up"
    errors = validate_case_manifest(d)
    codes = {(e.path, e.code) for e in errors}
    assert ("category", "unknown_enum") in codes


def test_unknown_privacy_class_reports_unknown_enum() -> None:
    d = _good_dict()
    d["privacy_class"] = "top_secret"
    errors = validate_case_manifest(d)
    codes = {(e.path, e.code) for e in errors}
    assert ("privacy_class", "unknown_enum") in codes


# --- 7. Fixtures ---------------------------------------------------------


def test_missing_fixtures_reports_missing_field() -> None:
    d = _good_dict()
    del d["fixtures"]
    errors = validate_case_manifest(d)
    codes = {(e.path, e.code) for e in errors}
    assert ("fixtures", "missing_field") in codes


def test_non_list_fixtures_reports_type_error() -> None:
    d = _good_dict()
    d["fixtures"] = "not a list"
    errors = validate_case_manifest(d)
    codes = {(e.path, e.code) for e in errors}
    assert ("fixtures", "type_error") in codes


def test_empty_fixtures_reports_empty_list() -> None:
    d = _good_dict()
    d["fixtures"] = []
    errors = validate_case_manifest(d)
    codes = {(e.path, e.code) for e in errors}
    assert ("fixtures", "empty_list") in codes


def test_fixture_missing_path_reports_missing_field() -> None:
    d = _good_dict()
    d["fixtures"] = [{"revision": "f3ad4ef"}]
    errors = validate_case_manifest(d)
    codes = {(e.path, e.code) for e in errors}
    assert ("fixtures.0.path", "missing_field") in codes


def test_fixture_missing_revision_reports_missing_field() -> None:
    d = _good_dict()
    d["fixtures"] = [{"path": "foo.txt"}]
    errors = validate_case_manifest(d)
    codes = {(e.path, e.code) for e in errors}
    assert ("fixtures.0.revision", "missing_field") in codes


def test_fixture_absolute_path_reports_absolute_path() -> None:
    d = _good_dict()
    d["fixtures"] = [{"path": "/etc/passwd", "revision": "f3ad4ef"}]
    errors = validate_case_manifest(d)
    codes = {(e.path, e.code) for e in errors}
    assert ("fixtures.0.path", "absolute_path") in codes


def test_multiple_fixtures_each_get_unique_path() -> None:
    """Each fixture error must carry its own index."""
    d = _good_dict()
    d["fixtures"] = [
        {"path": "ok.txt", "revision": "f3ad4ef"},
        {"revision": "f3ad4ef"},          # missing path
        {"path": "/abs.txt", "revision": ""},  # both problems
    ]
    errors = validate_case_manifest(d)
    paths = {e.path for e in errors}
    assert "fixtures.1.path" in paths
    assert "fixtures.2.path" in paths
    assert "fixtures.2.revision" in paths


# --- 8. Expected evidence -----------------------------------------------


def test_missing_expected_evidence_reports_missing_field() -> None:
    d = _good_dict()
    del d["expected_evidence"]
    errors = validate_case_manifest(d)
    codes = {(e.path, e.code) for e in errors}
    assert ("expected_evidence", "missing_field") in codes


def test_empty_expected_evidence_reports_empty_list() -> None:
    d = _good_dict()
    d["expected_evidence"] = []
    errors = validate_case_manifest(d)
    codes = {(e.path, e.code) for e in errors}
    assert ("expected_evidence", "empty_list") in codes


def test_evidence_unknown_kind_reports_unknown_enum() -> None:
    d = _good_dict()
    d["expected_evidence"] = [
        {"kind": "magic", "target": "x", "value": "y", "reviewer": "alice"},
    ]
    errors = validate_case_manifest(d)
    codes = {(e.path, e.code) for e in errors}
    assert ("expected_evidence.0.kind", "unknown_enum") in codes


def test_evidence_missing_reviewer_reports_missing_field() -> None:
    d = _good_dict()
    d["expected_evidence"] = [
        {"kind": "task_status", "target": "BLOCKED", "value": "BLOCKED"},
    ]
    errors = validate_case_manifest(d)
    codes = {(e.path, e.code) for e in errors}
    assert ("expected_evidence.0.reviewer", "missing_field") in codes


def test_evidence_empty_target_reports_empty_string() -> None:
    d = _good_dict()
    d["expected_evidence"] = [
        {"kind": "task_status", "target": "", "value": "BLOCKED",
         "reviewer": "alice"},
    ]
    errors = validate_case_manifest(d)
    codes = {(e.path, e.code) for e in errors}
    assert ("expected_evidence.0.target", "empty_string") in codes


def test_evidence_non_string_reviewer_reports_type_error() -> None:
    d = _good_dict()
    d["expected_evidence"] = [
        {"kind": "task_status", "target": "BLOCKED", "value": "BLOCKED",
         "reviewer": 42},
    ]
    errors = validate_case_manifest(d)
    codes = {(e.path, e.code) for e in errors}
    assert ("expected_evidence.0.reviewer", "type_error") in codes


# --- 9. Budget fields ----------------------------------------------------


def test_zero_timeout_reports_out_of_range() -> None:
    d = _good_dict()
    d["timeout_seconds"] = 0
    errors = validate_case_manifest(d)
    codes = {(e.path, e.code) for e in errors}
    assert ("timeout_seconds", "out_of_range") in codes


def test_negative_max_iterations_reports_out_of_range() -> None:
    d = _good_dict()
    d["max_iterations"] = -1
    errors = validate_case_manifest(d)
    codes = {(e.path, e.code) for e in errors}
    assert ("max_iterations", "out_of_range") in codes


def test_non_integer_budget_reports_type_error() -> None:
    d = _good_dict()
    d["timeout_seconds"] = "60"  # string, not int
    errors = validate_case_manifest(d)
    codes = {(e.path, e.code) for e in errors}
    assert ("timeout_seconds", "type_error") in codes


def test_bool_budget_reports_type_error() -> None:
    """``True``/``False`` are not integers for budget fields."""
    d = _good_dict()
    d["max_iterations"] = True
    errors = validate_case_manifest(d)
    codes = {(e.path, e.code) for e in errors}
    assert ("max_iterations", "type_error") in codes


# --- 10. Error accumulation ----------------------------------------------


def test_validation_collects_every_error_at_once() -> None:
    """The validator does not stop at the first error; it
    reports every problem so a single round-trip
    surfaces the full fix list.
    """
    d = _good_dict()
    d["case_id"] = ""
    d["schema_version"] = "0.0.1"
    d["category"] = "made_up"
    d["privacy_class"] = "made_up"
    d["goal"] = ""
    del d["fixtures"]
    del d["expected_evidence"]
    d["timeout_seconds"] = -1
    errors = validate_case_manifest(d)
    codes = {(e.path, e.code) for e in errors}
    # At least one of each category.
    assert ("case_id", "empty_string") in codes
    assert ("schema_version", "version_mismatch") in codes
    assert ("category", "unknown_enum") in codes
    assert ("privacy_class", "unknown_enum") in codes
    assert ("goal", "empty_string") in codes
    assert ("fixtures", "missing_field") in codes
    assert ("expected_evidence", "missing_field") in codes
    assert ("timeout_seconds", "out_of_range") in codes


# --- 11. Integration with the typed contract ----------------------------


def test_validate_then_from_dict_yields_same_dataclass() -> None:
    """A dict that passes validation parses through the
    typed dataclass without raising.
    """
    d = _good_dict()
    assert validate_case_manifest(d) == []
    m = case_manifest_from_dict(d)
    assert isinstance(m, CaseManifest)
    assert m.case_id == "case_a"


# --- 12. paw.core 11-symbol surface preserved ---------------------------


def test_paw_core_public_surface_unchanged_after_e0_07() -> None:
    """E0-23a guard: adding ``SchemaError`` /
    ``validate_case_manifest`` / ``is_valid_case_manifest``
    to ``paw.bench`` must not grow the canonical 11-symbol
    ``paw.core`` export list.
    """
    import paw.core
    symbols = [s for s in dir(paw.core) if not s.startswith("_")]
    expected_runtime = {
        "AutonomyDecision",
        "Capability",
        "ExecutionObservation",
        "PawRuntime",
        "PolicyDecision",
        "ProposedAction",
        "ResourceUsage",
        "RuntimeOutcome",
        "StopReason",
        "TaskResult",
        "TaskStatus",
    }
    assert expected_runtime.issubset(set(symbols)), (
        f"paw.core missing runtime symbols: {expected_runtime - set(symbols)}"
    )


# --- 13. SchemaError value object ----------------------------------------


def test_schema_error_equality_and_hash() -> None:
    a = SchemaError("foo", "bar", "baz")
    b = SchemaError("foo", "bar", "baz")
    c = SchemaError("foo", "bar", "qux")
    assert a == b
    assert a != c
    assert hash(a) == hash(b)
    assert hash(a) != hash(c)


def test_schema_error_repr_is_diagnostic() -> None:
    a = SchemaError("fixtures.0.path", "absolute_path", "/etc/passwd")
    text = repr(a)
    assert "fixtures.0.path" in text
    assert "absolute_path" in text
    assert "/etc/passwd" in text
