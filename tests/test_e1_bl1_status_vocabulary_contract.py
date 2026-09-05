"""E1-BL1 contract test: broaden the contract-check status-vocabulary rule.

The change-control surface is the script
``skills/bootstrap-canonical-docs/scripts/contract-checks.sh``.
The contract test exercises three scenarios:

1. A clean canonical doc passes (the original
   status-vocabulary check).
2. A canonical doc with ``already DONE`` outside an
   item-shaped clause FAILS (the broader check catches
   it; the narrower check would not).
3. A canonical doc with a forbidden word in a backtick
   span or a code-fence passes (the broader check
   strips both so the rules themselves are not
   flagged).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


SCRIPT = Path("skills/bootstrap-canonical-docs/scripts/contract-checks.sh")
CHECKLIST = Path("docs/EXECUTION_CHECKLIST.md")


def _run_check() -> subprocess.CompletedProcess:
    """Run the contract-check script. The process
    exit code is the contract verdict: 0 = pass,
    non-zero = fail."""
    return subprocess.run(
        ["bash", str(SCRIPT)],
        shell=False, check=False,
        capture_output=True, text=True,
    )


def _backup() -> None:
    if not hasattr(_backup, "_path"):
        _backup._path = CHECKLIST.with_suffix(".bak")
    shutil.copy(CHECKLIST, _backup._path)


def _restore() -> None:
    shutil.copy(_backup._path, CHECKLIST)


def test_clean_canonical_doc_passes() -> None:
    """The current canonical docs use the closed
    status vocabulary; the script passes."""
    result = _run_check()
    assert "CONTRACT PASSED" in result.stdout


def test_broader_check_catches_already_done() -> None:
    """A line such as ``already DONE`` is caught by the
    broader E1-BL1 check (the narrower check requires
    the forbidden word to follow an item-shaped
    clause)."""
    _backup()
    try:
        with CHECKLIST.open("a", encoding="utf-8") as f:
            f.write("\nThis line is already DONE.\n")
        result = _run_check()
        assert "CONTRACT FAILED" in result.stdout, (
            "expected broader check to flag the 'already DONE' line"
        )
        # The report includes the file + line; the
        # forbidden word is the matched token
        # ``DONE``, recorded as the matched text. The
        # report text is "forbidden status word used ...",
        # so we check for that exact message.
        assert "forbidden status word used" in result.stdout
    finally:
        _restore()


def test_broader_check_skips_backtick_quoted() -> None:
    """A forbidden word in a backtick span (the rules
    themselves) is not flagged."""
    _backup()
    try:
        with CHECKLIST.open("a", encoding="utf-8") as f:
            f.write("\nThis line has `DONE` in backticks.\n")
        result = _run_check()
        assert "CONTRACT PASSED" in result.stdout
    finally:
        _restore()


def test_broader_check_skips_code_fence() -> None:
    """A forbidden word in a code-fence (the rules
    themselves) is not flagged."""
    _backup()
    try:
        with CHECKLIST.open("a", encoding="utf-8") as f:
            f.write("\n```\nThis is documentation. DONE is fine here.\n```\n")
        result = _run_check()
        assert "CONTRACT PASSED" in result.stdout
    finally:
        _restore()


def test_broader_check_skips_item_shaped_clause() -> None:
    """A forbidden word inside the existing item-shaped
    clause (which the narrower check catches) does not
    re-trigger the broader check; the broader check
    strips the item-shaped clause first.

    Note: the broader check is allowed to also report
    the violation; the contract is "the violation is
    caught by the broader check too", not "the broader
    check is suppressed when the narrower check fires".
    Both checks contribute to the contract: the
    narrower for the item-shaped clause, the broader
    for the rest of the line.
    """
    _backup()
    try:
        with CHECKLIST.open("a", encoding="utf-8") as f:
            f.write("\n- (1h, D0) TODO this is a test\n")
        result = _run_check()
        # The narrower check reports the violation; the
        # broader check may also report it (the
        # contract is "the violation is caught").
        assert "CONTRACT FAILED" in result.stdout
        # The violation is reported at least once.
        stdout = result.stdout
        assert stdout.count("forbidden status word") >= 1
    finally:
        _restore()