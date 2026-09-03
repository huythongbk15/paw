#!/usr/bin/env bash
# Selective test runner for doc-driven-stabilization.
#
# Maps the verification level (D0-D3) to the smallest
# test command that proves the item. Avoids running the
# full suite after every D1 item.
#
# Usage:
#   ./scripts/pt.sh D1 test_e0_case_manifest.py
#   ./scripts/pt.sh D2 test_runtime_atomicity.py test_external_effect_reconciliation.py
#   ./scripts/pt.sh D3
#   ./scripts/pt.sh D0 docs            # git grep only, no pytest
#
# Levels:
#   D0  Docs only — runs `git grep` checks, no pytest.
#   D1  Focused   — runs pytest on the named test file(s).
#   D2  Integ.    — runs pytest on named files + the critical-path set
#                  (test_project_lock, test_phase6_security, test_runtime_atomicity).
#   D3  Release   — runs the full suite once. Use only at freeze
#                  or cross-track milestones.

set -euo pipefail

LEVEL="${1:-D1}"
shift || true

cd "$(git rev-parse --show-toplevel)"

# Critical-path tests always run for D2+ (impact surface).
CRITICAL_PATH=(
    tests/test_project_lock.py
    tests/test_phase6_security.py
    tests/test_runtime_atomicity.py
)

case "$LEVEL" in
    D0)
        # No tests. Run a couple of grep-based hygiene checks.
        echo "[D0] running git grep hygiene checks"
        if grep -rn "TODO\|FIXME\|XXX" docs/IMPLEMENTATION_MAP.md docs/ROADMAP.md 2>/dev/null; then
            echo "[D0] WARN: forbidden words found in canonical docs"
        fi
        if grep -rn "current_phase\|current[ _]phase\s*[:=]" docs/ 2>/dev/null; then
            echo "[D0] FAIL: stale 'current phase' marker found"
            exit 1
        fi
        echo "[D0] OK"
        ;;
    D1)
        if [[ $# -eq 0 ]]; then
            echo "usage: $0 D1 <test_file> [<test_file> ...]" >&2
            exit 2
        fi
        echo "[D1] running focused tests: $*"
        .venv/bin/python -m pytest "$@" -q
        ;;
    D2)
        targets=("$@")
        if [[ ${#targets[@]} -eq 0 ]]; then
            echo "usage: $0 D2 <test_file> [<test_file> ...]" >&2
            exit 2
        fi
        all=("${targets[@]}" "${CRITICAL_PATH[@]}")
        # Dedup
        unique=($(printf "%s\n" "${all[@]}" | sort -u))
        echo "[D2] running focused + critical-path: ${unique[*]}"
        .venv/bin/python -m pytest "${unique[@]}" -q
        ;;
    D3)
        echo "[D3] running FULL suite (this is slow; use only at freeze)"
        .venv/bin/python -m pytest -q
        .venv/bin/python -m ruff check .
        ;;
    *)
        echo "unknown level: $LEVEL (expected D0, D1, D2, D3)" >&2
        exit 2
        ;;
esac
