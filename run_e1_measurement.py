#!/usr/bin/env python3
"""E1-23/24/25 real measurement on PAW source repo.

Minimal run: 2 representative cases, produces a decision report.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from datetime import UTC, datetime
from statistics import median

from paw.bench.integration import run_integration_pack
from paw.core.context_compiler import ContextCompiler, ContextBudget

REPO_ROOT = Path("/home/huythong/.hybridagent/workspaces/default")
CASE_DIR = REPO_ROOT / "benchmarks" / "e1" / "cases_subset"
REPORT_PATH = REPO_ROOT / "benchmarks" / "e1" / "e1_real_measurement_report.md"

BASELINE_TOKENS = {
    "architecture_decision_cache": 4000,
    "cross_module_change_constant": 3000,
}

async def main():
    compiler = ContextCompiler(
        budget=ContextBudget(max_tokens=8000, max_content_length=20000),
        auto_attach_embeddings=False,
    )
    
    print("Running E1 integration pack...")
    result = await run_integration_pack(
        CASE_DIR,
        compiler=compiler,
        repo_root=REPO_ROOT,
        report_path=REPORT_PATH,
        baseline_tokens=BASELINE_TOKENS,
    )
    
    # Print results
    print(f"\nGate: {result.gate_decision}")
    print(f"Cases: {result.case_count}")
    for r in result.recall_results:
        print(f"  Recall: {r.case_id} recall={r.recall:.2f} mode={r.mode}")
    for t in result.token_results:
        print(f"  Tokens: {t.case_id} baseline={t.baseline_tokens} measured={t.measured_tokens} reduction={t.reduction:.2f} mode={t.mode}")
    
    print(f"\nReport: {REPORT_PATH}")
    print(REPORT_PATH.read_text())

asyncio.run(main())
