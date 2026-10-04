#!/usr/bin/env python3
"""E0-21 — run the approved cloud baseline and record observed usage.

Profile: docs/benchmarks/e0/cloud_baseline_profile.md.

For each reviewed case, PAW compiles the context manifest from the foreign
corpus with its normal retrieval path, that manifest is handed to the routed
cloud model and nothing else, and the answer is scored against the case's own
expected evidence using the same ``file_contains`` rule the offline runner uses.

Usage and cost come from the provider's own response, so both are **observed**.
On OpenRouter the response carries a real ``cost`` field, so even cost is
observed rather than estimated from a price table.

Free-tier models are rate limited and intermittently return 429. That is a
property of the free tier, not a PAW failure, so the runner falls back across a
declared model list and records which model actually answered per case.

Manual and opt-in: it makes network calls and therefore must never run in the
default suite.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import pathlib
import sys
import urllib.error
import urllib.request

PAW_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PAW_ROOT / "src"))
logging.disable(logging.CRITICAL)
import structlog  # noqa: E402

structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL))
import yaml  # noqa: E402

from paw.core.context import ContextBudget  # noqa: E402
from paw.core.context_compiler import ContextCompiler  # noqa: E402
from paw.core.privacy import PrivacyClass, can_disclose_to_provider  # noqa: E402
from paw.core.storage import db, set_db_path  # noqa: E402

DEFAULT_MODELS = [
    "nvidia/nemotron-3.5-lightning:free",
    "qwen/qwen3.8-27b:free",
    "google/gemma-4-31b-it:free",
]
URL = "https://openrouter.ai/api/v1/chat/completions"
CAP_USD = float(os.environ.get("PAW_CLOUD_CAP_USD", "0.05"))


def call_cloud(model: str, messages: list[dict], max_tokens: int,
               timeout: int = 180) -> tuple[str, dict]:
    body = json.dumps({
        "model": model, "messages": messages, "temperature": 0,
        "max_tokens": max_tokens,
    }).encode()
    request = urllib.request.Request(
        URL, data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
                 "HTTP-Referer": "https://github.com/paw", "X-Title": "PAW"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    usage = payload.get("usage", {}) or {}
    text = (payload.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
    return text, {
        "model": model,
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
        "cost_usd": usage.get("cost"),          # observed, reported by the provider
        "cost_observed": usage.get("cost") is not None,
    }


def evidence_of(row: dict) -> bool:
    return row["kind"] == "file_contains" and bool(row.get("value"))


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-dir", type=pathlib.Path,
                        default=PAW_ROOT / "benchmarks/e1/cases_foreign")
    parser.add_argument("--output", type=pathlib.Path,
                        default=pathlib.Path("/tmp/paw-e2e/e0_21_cloud_baseline.json"))
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    parser.add_argument("--max-tokens", type=int, default=900)
    parser.add_argument("--attempts-per-case", type=int, default=6)
    args = parser.parse_args()

    await set_db_path(pathlib.Path("/tmp/paw-e2e/paw-e0-21.db"))
    await db.initialize()

    # Disclosure gate, enforced before any request. SECRET never leaves the machine.
    assert can_disclose_to_provider(PrivacyClass.INTERNAL, "cloud_approved")
    assert not can_disclose_to_provider(PrivacyClass.SECRET, "cloud_approved")

    compiler = ContextCompiler(
        budget=ContextBudget(max_tokens=6000, max_fragments=30, max_sources=10),
        auto_attach_embeddings=False,
    )
    report = {"router": "openrouter", "models_declared": args.models,
              "cap_usd": CAP_USD, "cases": [], "attempts": []}
    total_cost = 0.0

    for case_path in sorted(args.case_dir.glob("*.yaml")):
        raw = yaml.safe_load(case_path.read_text(encoding="utf-8"))
        if "negative-control" in (raw.get("tags") or []):
            continue                     # a case that must fail is not scored here
        evidence = [e for e in raw["expected_evidence"] if evidence_of(e)]
        if not evidence:
            continue

        manifest = await compiler.compile_manifest(raw["case_id"], raw["goal"])
        context = "\n\n".join(
            f"--- {item.external_id or item.reference}\n{item.content}"
            for item in manifest.included
            if (item.metadata.get("privacy_class") or PrivacyClass.INTERNAL)
            != PrivacyClass.SECRET
        )
        messages = [
            {"role": "system", "content":
             "You are a precise code-analysis assistant. Use ONLY the context "
             "provided. If the context is insufficient, say so explicitly."},
            {"role": "user", "content":
             f"TASK:\n{raw['goal']}\n\nCONTEXT:\n{context}\n\n"
             "Answer with the exact source lines that satisfy the task, verbatim."},
        ]

        answer, usage, answered_model, tried = "", {}, None, []
        for attempt in range(args.attempts_per_case):
            model = args.models[attempt % len(args.models)]
            tried.append(model)
            report["attempts"].append({"case": raw["case_id"], "model": model,
                                       "attempt": attempt})
            try:
                answer, usage = await asyncio.to_thread(
                    call_cloud, model, messages, args.max_tokens)
                answered_model = model
                break
            except urllib.error.HTTPError as exc:
                report["attempts"][-1]["http_error"] = exc.code
                if exc.code not in (429, 502, 503, 504):
                    break
                await asyncio.sleep(2.0)
            except Exception as exc:
                report["attempts"][-1]["error"] = f"{type(exc).__name__}: {exc}"
                await asyncio.sleep(2.0)

        cost = float(usage.get("cost_usd") or 0.0)
        total_cost += cost
        found = [e["value"] for e in evidence if e["value"] in (answer or "")]
        report["cases"].append({
            "case_id": raw["case_id"],
            "answered": bool((answer or "").strip()),
            "model": answered_model,
            "models_tried": tried,
            "recall": round(len(found) / len(evidence), 4) if evidence else 0.0,
            "evidence_found": len(found), "evidence_total": len(evidence),
            "fragments_sent": len(manifest.included),
            "context_tokens": manifest.final_tokens,
            "usage": usage,
        })
        print(f"  {raw['case_id'][:44]:46} recall={len(found)}/{len(evidence)} "
              f"cost=${cost:.6f} model={answered_model}", flush=True)
        if total_cost > CAP_USD:
            print(f"  ABORT: observed spend {total_cost:.6f} exceeds cap {CAP_USD}")
            report["aborted_on_cap"] = True
            break

    recalls = [c["recall"] for c in report["cases"]]
    report["case_count"] = len(report["cases"])
    report["mean_recall"] = round(sum(recalls) / len(recalls), 4) if recalls else 0.0
    report["min_recall"] = min(recalls) if recalls else 0.0
    report["observed_total_tokens"] = sum(
        c["usage"].get("total_tokens", 0) for c in report["cases"])
    report["observed_total_cost_usd"] = round(total_cost, 6)
    report["cost_observed"] = all(
        c["usage"].get("cost_observed", False) for c in report["cases"] if c["answered"])
    report["usage_source"] = "provider usage block (observed, not estimated)"
    await db.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2))
    print(f"\n  cases={report['case_count']} mean_recall={report['mean_recall']} "
          f"min_recall={report['min_recall']}")
    print(f"  OBSERVED tokens={report['observed_total_tokens']} "
          f"cost=${report['observed_total_cost_usd']} (cap ${CAP_USD})")
    print(f"  -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
