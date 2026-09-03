"""Reproducible PAW-only dependency baseline contract."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = PROJECT_ROOT / "pyproject.toml"
UV_LOCK = PROJECT_ROOT / "uv.lock"
CANONICAL_DOCS = (
    "README.md",
    "PRODUCT_CHARTER.md",
    "ARCHITECTURE.md",
    "IMPLEMENTATION_MAP.md",
    "ROADMAP.md",
    "ENGINEERING_RULES.md",
    "EXECUTION_CHECKLIST.md",
)


def _dependency_name(requirement: str) -> str:
    return re.split(r"[<>=!~\[; ]", requirement, maxsplit=1)[0].lower()


def test_uv_lock_contains_only_project_declared_dependency_graph() -> None:
    assert UV_LOCK.is_file(), "uv.lock is the canonical PAW dependency lock"
    assert not (PROJECT_ROOT / "requirements.lock.txt").exists(), (
        "the captured host environment must not compete with the PAW lock"
    )
    ignored_lines = {
        line.strip().lstrip("/")
        for line in (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert "uv.lock" not in ignored_lines

    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    lock = tomllib.loads(UV_LOCK.read_text(encoding="utf-8"))
    packages = {package["name"].lower() for package in lock["package"]}
    declared = {
        _dependency_name(requirement)
        for requirement in (
            project["project"]["dependencies"]
            + project["project"]["optional-dependencies"]["dev"]
        )
    }

    assert "paw" in packages
    assert declared <= packages
    assert packages.isdisjoint(
        {"anthropic", "boto3", "celery", "kafka-python", "redis"}
    )


def test_canonical_docs_do_not_restore_stale_phase_or_module_claims() -> None:
    contents = {
        name: (PROJECT_ROOT / "docs" / name).read_text(encoding="utf-8")
        for name in CANONICAL_DOCS
    }
    combined = "\n".join(contents.values())

    assert "requirements.lock.txt" not in combined
    assert "intelligent_planner.py" not in combined
    assert not re.search(r"(?mi)^\s*current[_ ]phase\s*[:=]", combined)

    source_refs = set(
        re.findall(
            r"`((?:application|core|executors|knowledge|providers)/"
            r"[a-zA-Z0-9_/]+\.py)`",
            combined,
        )
    )
    assert source_refs, "canonical docs must contain checked source references"
    missing = [
        ref
        for ref in sorted(source_refs)
        if not (PROJECT_ROOT / "src" / "paw" / ref).is_file()
    ]
    assert missing == []


def test_post_gate_research_contract_blocks_non_ready_implementation() -> None:
    architecture = (PROJECT_ROOT / "docs" / "ARCHITECTURE.md").read_text(
        encoding="utf-8"
    )
    implementation_map = (
        PROJECT_ROOT / "docs" / "IMPLEMENTATION_MAP.md"
    ).read_text(encoding="utf-8")
    roadmap = (PROJECT_ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")

    for readiness in (
        "NEEDS_RESEARCH",
        "NEEDS_CLARIFICATION",
        "SPIKE_REQUIRED",
        "READY",
        "REJECTED",
    ):
        assert readiness in architecture
        assert readiness in roadmap

    assert "ImplementationReadiness" in architecture
    assert "An implementation-purpose `Plan`" in architecture
    assert "Evidence-before-implementation gap" in implementation_map
    assert "not a claim about the current runtime" in architecture


def test_status_and_post_gate_sequence_are_unambiguous() -> None:
    docs_readme = (PROJECT_ROOT / "docs" / "README.md").read_text(
        encoding="utf-8"
    )
    roadmap = (PROJECT_ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")

    assert "Status has two separate dimensions" in docs_readme
    assert "`DONE` and bare `implemented` are not status labels" in docs_readme
    assert "| Core Stabilization exit gate | `PARTIAL` |" in roadmap
    assert "| E0–E3 and BETA | `BLOCKED` |" in roadmap
    assert "E0 → E1 → E2 → E3 → BETA" in roadmap
    assert "### BETA — Daily engineering-partner validation" in roadmap
    assert "E4 training is not required to pass this gate" in roadmap


def test_ratified_post_gate_boundaries_extend_existing_owners() -> None:
    charter = (PROJECT_ROOT / "docs" / "PRODUCT_CHARTER.md").read_text(
        encoding="utf-8"
    )
    architecture = (PROJECT_ROOT / "docs" / "ARCHITECTURE.md").read_text(
        encoding="utf-8"
    )
    implementation_map = (
        PROJECT_ROOT / "docs" / "IMPLEMENTATION_MAP.md"
    ).read_text(encoding="utf-8")
    roadmap = (PROJECT_ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")

    assert "PAW does not introduce a `ResearchTask`" in charter
    assert "RESEARCH | SPIKE | IMPLEMENTATION" in architecture
    assert "DRAFT | FINAL | STALE | SUPERSEDED" in architecture
    assert "VerificationSpec" in architecture
    assert "VerificationRecord" in architecture
    assert "`ESCALATE` is a non-terminal control transition" in architecture
    assert "`SkillFabric` remains the sole skill registry" in architecture
    assert "Through BETA, PAW assumes one local user authority" in architecture

    assert "Planner.plan(task_id)" in implementation_map
    assert "Unknown Tasks fail before Plan/node writes" in implementation_map
    assert "ExecutionObservation.success" in implementation_map
    assert "runtime handles it as a stopped outcome" in implementation_map
    assert "benchmark construction does not depend on E1–E3" in architecture
    assert "one Task with typed Plan purpose" in roadmap
