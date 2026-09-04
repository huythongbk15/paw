"""E1-01 contract test: ownership audit pinned to source dataclasses (D1).

The audit lives at ``docs/benchmarks/e1/ownership_audit.md``.
The contract is: every field listed in the audit must
still exist on the corresponding dataclass in the source;
every dataclass field the audit names must appear in the
audit's field table. When a new field lands in one of the
owned dataclasses, the audit must be regenerated in the
same commit and this test must still pass.

The audit is regenerated from source by hand; this test
only verifies that the audit's claimed field list matches
the dataclass field list. It does not enforce the *order*
of fields and it does not enforce the *description text*;
both are the audit author's responsibility.

Two-fail-positive discipline: this test was added because
the E1-01 audit listed a phantom ``source`` field on
``MemoryRecord`` and missed several real fields
(``keywords``, ``updated_at``, ``last_accessed``). The
audit is now regenerated from source.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
AUDIT_PATH = REPO_ROOT / "docs" / "benchmarks" / "e1" / "ownership_audit.md"


def _parse_field_rows(table_markdown: str) -> set[str]:
    """Extract field names from a markdown table whose
    first column is ``Field`` (header line begins with
    ``| Field`` or ``| field on ``)."""
    rows: set[str] = set()
    for line in table_markdown.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells:
            continue
        first = cells[0]
        # Skip header rows and separator rows.
        if first.lower().startswith("field") or first == "---" or set(first) <= {"-", " "}:
            continue
        # Field name is the first cell, in backticks.
        m = re.match(r"`?([A-Za-z_][A-Za-z0-9_]*)`?", first)
        if m:
            rows.add(m.group(1))
    return rows


def _table_under_heading(audit_text: str, heading: str) -> str:
    """Return the markdown block starting at the heading
    ``heading`` and ending at the next heading of equal-or-
    lower level. Both ``## `` and ``### `` headings are
    recognized; the block stops at the *first* heading whose
    marker depth is ≤ the start heading's depth."""
    start_idx = audit_text.find(heading)
    if start_idx < 0:
        return ""
    # Determine the start heading depth.
    tail = audit_text[start_idx:]
    lines = tail.splitlines()
    if not lines:
        return ""
    # Skip the heading line.
    start_depth = len(lines[0]) - len(lines[0].lstrip("#"))
    block: list[str] = []
    found_heading = False
    for line in lines:
        if not found_heading:
            found_heading = True
            continue
        if line.startswith("#"):
            stripped = line.lstrip("#")
            depth = len(line) - len(stripped)
            if depth <= start_depth:
                break
        block.append(line)
    return "\n".join(block)


# --- Import the owned dataclasses ----------------------------------------


def _import_dataclass(qualname: str):
    """Late import so the test file does not need a hard
    dependency on the runtime path; the modules are imported
    here only when the test runs."""
    import importlib

    module_name, _, class_name = qualname.rpartition(".")
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


DATACLASS_OWNERS = {
    "MemoryRecord":         "paw.core.memory.MemoryRecord",
    "KnowledgeSource":      "paw.knowledge.source.KnowledgeSource",
    "KnowledgeChunk":       "paw.knowledge.chunk.KnowledgeChunk",
    "KnowledgeEvidence":    "paw.knowledge.evidence.KnowledgeEvidence",
    "KnowledgeCitation":    "paw.knowledge.citation.KnowledgeCitation",
    "TaskContext":          "paw.core.context.TaskContext",
    "ContextBudget":        "paw.core.context.ContextBudget",
}


# --- The contract --------------------------------------------------------


@pytest.mark.parametrize(
    "audit_label,class_qualname", sorted(DATACLASS_OWNERS.items())
)
def test_every_audited_field_is_real_dataclass_field(audit_label, class_qualname):
    """Every field listed in the audit's table must be a
    real ``dataclasses.field`` on the owned dataclass."""
    audit_text = AUDIT_PATH.read_text(encoding="utf-8")
    # Find the audit section for this dataclass.
    # The audit uses the dataclass name in headings like
    # "MemoryRecord declares 16 fields" or "KnowledgeSource
    # (12 fields)".
    heading_re = re.escape(audit_label)
    if audit_label in {"MemoryRecord", "TaskContext", "ContextBudget"}:
        # These are under a different heading style.
        if audit_label == "MemoryRecord":
            block = _table_under_heading(audit_text, "## Memory")
        elif audit_label == "TaskContext":
            block = _table_under_heading(audit_text, "### `TaskContext`")
        else:  # ContextBudget
            block = _table_under_heading(audit_text, "### `ContextBudget`")
    else:
        # KnowledgeX uses headings like ``### `chunk.py` —
        # `KnowledgeChunk` (7 fields)``.
        block = _table_under_heading(
            audit_text,
            f"### `{audit_label.replace('Knowledge', '').lower()}.py`",
        )
        if not block:
            # Fallback: search for the dataclass name directly.
            block = _table_under_heading(audit_text, audit_label)
    assert block, f"no audit table found for {audit_label}"

    audited = _parse_field_rows(block)
    cls = _import_dataclass(class_qualname)
    actual = {f.name for f in dataclasses.fields(cls)}

    # 1. Every audited field is a real field on the dataclass.
    missing = audited - actual
    assert not missing, (
        f"{audit_label}: audit lists phantom fields {sorted(missing)}; "
        f"regenerate the audit from source. Real fields: {sorted(actual)}."
    )


@pytest.mark.parametrize(
    "audit_label,class_qualname", sorted(DATACLASS_OWNERS.items())
)
def test_audit_does_not_drop_existing_fields(audit_label, class_qualname):
    """The audit must list every field on the dataclass except
    those documented as "transient / not persisted" (e.g.
    ``KnowledgeSearchResult``). This guards against the
    previous regression where the audit dropped
    `keywords`, `updated_at`, `last_accessed` from
    ``MemoryRecord``."""

    audit_text = AUDIT_PATH.read_text(encoding="utf-8")
    if audit_label == "MemoryRecord":
        block = _table_under_heading(audit_text, "## Memory")
    elif audit_label == "TaskContext":
        block = _table_under_heading(audit_text, "### `TaskContext`")
    elif audit_label == "ContextBudget":
        block = _table_under_heading(audit_text, "### `ContextBudget`")
    else:
        block = _table_under_heading(
            audit_text,
            f"### `{audit_label.replace('Knowledge', '').lower()}.py`",
        )
        if not block:
            block = _table_under_heading(audit_text, audit_label)
    assert block, f"no audit table found for {audit_label}"

    audited = _parse_field_rows(block)
    cls = _import_dataclass(class_qualname)
    actual = {f.name for f in dataclasses.fields(cls)}

    # 2. Every dataclass field is listed in the audit.
    dropped = actual - audited
    assert not dropped, (
        f"{audit_label}: audit is missing real fields {sorted(dropped)}; "
        f"regenerate the audit from source. Actual fields: {sorted(actual)}."
    )


def test_audit_does_not_list_phantom_memory_source_field():
    """The original E1-01 audit listed a phantom ``source``
    field on ``MemoryRecord``. The regenerated audit must
    list exactly the 13 documented fields (12 dataclass
    fields minus ``id``, which is named in the audit
    header but counted in the field table) — actually
    13 rows in the table. This test pins that count so
    a future regression to the phantom field is caught."""
    audit_text = AUDIT_PATH.read_text(encoding="utf-8")
    block = _table_under_heading(audit_text, "## Memory")
    rows = _parse_field_rows(block)
    assert "source" not in rows, (
        "phantom 'source' field reappeared on MemoryRecord audit"
    )
    # The audit must list exactly the documented fields.
    expected = {
        "id",
        "project_id",
        "task_id",
        "memory_type",
        "content",
        "summary",
        "keywords",
        "metadata",
        "confidence",
        "created_at",
        "updated_at",
        "last_accessed",
        "access_count",
    }
    assert rows == expected, (
        f"MemoryRecord audit field set drifted: extra={rows - expected}, "
        f"missing={expected - rows}"
    )


def test_audit_documents_knowledge_source_real_fields():
    """The original E1-01 audit listed phantom KnowledgeSource
    fields (``kind``, ``uri``, ``revision``) instead of the
    real ones (``name``, ``type``, ``path``, ``status``,
    ``chunk_count``, ``last_sync``, ``checksum``,
    ``updated_at``). The regenerated audit must list the
    real field set."""
    audit_text = AUDIT_PATH.read_text(encoding="utf-8")
    block = _table_under_heading(audit_text, "### `source.py`")
    rows = _parse_field_rows(block)
    for phantom in {"kind", "uri", "revision"}:
        assert phantom not in rows, (
            f"phantom KnowledgeSource field {phantom!r} reappeared in audit"
        )
    for real in {
        "name",
        "type",
        "path",
        "status",
        "chunk_count",
        "last_sync",
        "checksum",
        "updated_at",
    }:
        assert real in rows, (
            f"real KnowledgeSource field {real!r} missing from audit"
        )