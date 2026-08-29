"""
PAW Phase 10 — False-Green Defense (R)

Negative-control tests that catch "false green" claims:
- No prohibited vendor imports (QwenPaw/DeepSeek/NotebookLM/Antigravity)
- Policy ASK must NOT execute (ASK == STOP)
- Context budget must be respected (cannot exceed)
- Skill loading must exclude disabled skills
- Package must contain only runtime files (no test files, no zero-size)
- Prohibited dependency must not be present in wheel metadata
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SRC_ROOT = REPO_ROOT / "src" / "paw"
WHEEL_PATH = REPO_ROOT / "dist" / "paw-0.1.0-py3-none-any.whl"

# Vendors that must NEVER be imported (zero vendor lock-in)
PROHIBITED_VENDORS = [
    "qwenpaw",
    "deepseek",
    "notebooklm",
    "antigravity",
    "opencode",
    "claude_code",
    "codex",
]


def _scan_python_files(root: Path) -> list[Path]:
    return list(root.rglob("*.py"))


def test_no_prohibited_vendor_imports_in_source():
    """Negative control: source must not import prohibited vendors at runtime.

    This checks for actual import statements of the vendor packages themselves
    (e.g. `import qwenpaw`, `from notebooklm import ...`). It does NOT flag
    PAW's own compatibility modules under `paw.providers.<vendor>` (those are
    explicitly optional adapters and are not imported by core unless opted in).
    """
    violations = []
    for f in _scan_python_files(SRC_ROOT):
        text = f.read_text(encoding="utf-8", errors="ignore")
        for vendor in PROHIBITED_VENDORS:
            # Match `import <vendor>` or `from <vendor> import` at line start
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith(f"import {vendor}") or stripped.startswith(f"from {vendor} "):
                    # Exclude PAW's own compatibility module paths
                    if f"paw.providers.{vendor}" in stripped:
                        continue
                    violations.append((str(f), vendor, stripped))

    # We expect ZERO import-time dependencies on prohibited vendors
    assert not violations, f"Prohibited vendor imports found: {violations}"


def test_core_modules_exclude_prohibited_vendor_strings():
    """Negative control: core runtime modules must not reference prohibited vendors.

    Core modules (paw/core, paw/knowledge) are the runtime foundation and must
    remain vendor-free. Provider adapters are allowed as optional compatibility.
    """
    core_root = SRC_ROOT / "core"
    knowledge_root = SRC_ROOT / "knowledge"
    violations = []
    for root in (core_root, knowledge_root):
        for f in _scan_python_files(root):
            text = f.read_text(encoding="utf-8", errors="ignore").lower()
            for vendor in PROHIBITED_VENDORS:
                if vendor in text:
                    violations.append((str(f), vendor))
    assert not violations, f"Prohibited vendor references in core/knowledge: {violations}"


def test_no_prohibited_vendor_in_wheel_metadata():
    """Negative control: wheel must not declare prohibited vendor deps."""
    if not WHEEL_PATH.exists():
        pytest.skip("Wheel not built yet — run `python -m build --wheel`")

    z = zipfile.ZipFile(WHEEL_PATH)
    metadata = ""
    for name in z.namelist():
        if name.endswith("METADATA"):
            metadata = z.read(name).decode("utf-8", errors="ignore")
            break

    for vendor in PROHIBITED_VENDORS:
        assert vendor not in metadata.lower(), f"Prohibited vendor in wheel metadata: {vendor}"


@pytest.mark.asyncio
async def test_policy_ask_must_not_execute():
    """Negative control: a capability defaulting to ASK must NOT be executable."""
    from paw.core.policy import PolicyGuard
    from paw.core.models import Capability, PolicyDecision

    # Executable decisions are ALLOW / SANDBOX; ASK and DENY are NOT.
    EXECUTABLE = {PolicyDecision.ALLOW, PolicyDecision.SANDBOX}

    guard = PolicyGuard()
    decision = await guard.check(Capability.FILESYSTEM_WRITE, context={})
    assert decision == PolicyDecision.ASK
    # ASK must never be treated as executable
    assert decision not in EXECUTABLE


@pytest.mark.asyncio
async def test_policy_deny_must_not_execute():
    """Negative control: DENY must never be executable."""
    from paw.core.policy import PolicyGuard
    from paw.core.models import Capability, PolicyDecision

    EXECUTABLE = {PolicyDecision.ALLOW, PolicyDecision.SANDBOX}

    guard = PolicyGuard()
    decision = await guard.check(Capability.FILESYSTEM_DELETE, context={})
    assert decision == PolicyDecision.DENY
    assert decision not in EXECUTABLE


@pytest.mark.asyncio
async def test_policy_ask_never_equals_allow():
    """Negative control: ASK decision value must differ from ALLOW (no silent promotion)."""
    from paw.core.models import PolicyDecision

    assert PolicyDecision.ASK != PolicyDecision.ALLOW
    assert PolicyDecision.ASK.value != PolicyDecision.ALLOW.value


@pytest.mark.asyncio
async def test_context_budget_cannot_be_exceeded():
    """Negative control: selected fragments must respect fragment/source budget."""
    from paw.core.context_compiler import ContextCompiler
    from paw.core.context import ContextBudget
    from paw.core.storage import db, set_db_path

    db_path = REPO_ROOT / "tests" / ".paw_fg" / "paw.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    await set_db_path(db_path)
    await db.initialize()

    try:
        compiler = ContextCompiler()
        # Tiny budget
        tiny_budget = ContextBudget(max_tokens=50, max_fragments=2, max_sources=1)
        context, candidates = await compiler.compile(
            task_id="fg-budget",
            query="budget limit test",
            budget=tiny_budget,
            explain_mode=True,
        )
        selected = [c for c in candidates if c.metadata.get("included")]
        # Hard constraint: never exceed max_fragments
        assert len(selected) <= tiny_budget.max_fragments
        # Hard constraint: never exceed max_sources
        sources = {c.source for c in selected}
        assert len(sources) <= tiny_budget.max_sources
    finally:
        pass


@pytest.mark.asyncio
async def test_disabled_skills_not_loaded():
    """Negative control: disabled skills must be excluded from candidates."""
    from paw.core.skills import SkillFabric, SkillManifest
    from paw.core.models import Capability, SkillRisk

    fabric = SkillFabric.__new__(SkillFabric)
    enabled = SkillManifest(
        name="enabled_skill", version="1.0.0", description="e",
        category="testing", capabilities=[Capability.FILESYSTEM_READ],
        risk=SkillRisk.LOW, trigger="e", body="body", enabled=True,
    )
    disabled = SkillManifest(
        name="disabled_skill", version="1.0.0", description="d",
        category="testing", capabilities=[Capability.FILESYSTEM_READ],
        risk=SkillRisk.LOW, trigger="d", body="body", enabled=False,
    )
    fabric._manifest_index = {"enabled_skill": enabled, "disabled_skill": disabled}

    listed = fabric.list_skills(enabled_only=True)
    names = {s.name for s in listed}
    assert "enabled_skill" in names
    assert "disabled_skill" not in names


def test_wheel_contains_only_runtime_files():
    """Negative control: wheel must contain non-zero runtime py files, no tests."""
    if not WHEEL_PATH.exists():
        pytest.skip("Wheel not built yet — run `python -m build --wheel`")

    z = zipfile.ZipFile(WHEEL_PATH)
    py_files = [n for n in z.namelist() if n.endswith(".py")]

    # Must have non-zero runtime files
    assert py_files, "Wheel contains no .py files"
    runtime_files = [n for n in py_files if not n.startswith("paw/tests")]
    assert runtime_files, "Wheel contains no runtime files"

    # No test files should be packaged
    test_files = [n for n in py_files if "test" in n.lower()]
    assert not test_files, f"Test files leaked into wheel: {test_files}"

    # No zero-size runtime files
    zero_files = [n for n in runtime_files if z.getinfo(n).file_size == 0]
    assert not zero_files, f"Zero-size runtime files: {zero_files}"


def test_source_scan_finds_nonzero_runtime_files():
    """Negative control: source tree must have non-zero runtime py files."""
    py_files = _scan_python_files(SRC_ROOT)
    assert py_files, "No source .py files found"
    nonzero = [f for f in py_files if f.stat().st_size > 0]
    assert len(nonzero) == len(py_files), "Some source files are zero-size"
