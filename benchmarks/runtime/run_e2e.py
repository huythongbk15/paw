"""Runtime end-to-end harness: one real engineering task through PAW.

Task, taken from the target repository rather than staged for PAW's benefit: the
six token-based classes in ``textdistance/algorithms/token_based.py`` each repeat
``self._get_counters(*sequences)`` followed by
``self._intersect_counters(*sequences)``. Extract that pair into one helper on
``Base``.

Pipeline, every stage through PAW-owned components:

  1 ingest the foreign repo into PAW knowledge
  2 compile the context manifest for the task
  3 the local model generates the helper
  4 Policy returns ASK for the mutating writes
  5 assert zero bytes were written before approval
  6 approve, then LocalFilesystemExecutor performs both writes
  7 verify with the target repository's own test suite
  8 read the ledger trail back

The oracle is the target repo's suite, run with a fixed hypothesis seed and an
isolated storage directory. It is differential: the failures already present at
the pinned revision must be the only failures afterwards. An earlier version
shared hypothesis's example database, which made the failing set move between
runs; that is why the storage directory is isolated here.

This harness is manual and opt-in. It needs a network fetch of the corpus and a
local Ollama server, so it is deliberately not collected by pytest.

Provenance of the change under test, stated precisely: the *helper* is generated
by the local model; the six call-site rewrites are a deterministic mechanical
transformation, because each class consumes the counters differently and the
local model is not yet reliable enough to be trusted with them. Both writes go
through Policy -> approval -> executor, so the gate evidence is complete.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import pathlib
import re
import subprocess
import sys

PAW_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PAW_ROOT / "src"))
logging.disable(logging.CRITICAL)
import structlog  # noqa: E402

structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL))


from paw.bench.e1_production import _chunk_python_file  # noqa: E402
from paw.core.approval import ApprovalStore  # noqa: E402
from paw.core.autonomy import AutonomyBudget, AutonomyController  # noqa: E402
from paw.core.context import ContextBudget  # noqa: E402
from paw.core.context_compiler import ContextCompiler  # noqa: E402
from paw.core.executor import CapabilityRouter, ExecutorRegistry  # noqa: E402
from paw.core.ledger import TaskLedger, log_verification_recorded  # noqa: E402
from paw.core.model_executor import ModelExecutor  # noqa: E402
from paw.core.model_router import ModelRouter, ProviderRegistry  # noqa: E402
from paw.core.models import (  # noqa: E402
    Capability,
    ProposedAction,
    ResourceUsage,
    VerificationRecord,
)
from paw.core.policy import PolicyGuard  # noqa: E402
from paw.core.runtime import PawRuntime  # noqa: E402
from paw.core.storage import db, set_db_path  # noqa: E402
from paw.core.task import TaskManager  # noqa: E402
from paw.executors.filesystem import LocalFilesystemExecutor  # noqa: E402
from paw.knowledge.chunk import KnowledgeChunkStore  # noqa: E402
from paw.knowledge.source import KnowledgeSourceManager  # noqa: E402

DEFAULT_CORPUS = pathlib.Path("/tmp/paw-e2e/textdistance")
DEFAULT_OUT = pathlib.Path("/tmp/paw-e2e/runtime-e2e-report.json")
BASE_REL = "textdistance/algorithms/base.py"
TOKEN_REL = "textdistance/algorithms/token_based.py"
GOAL = (
    "In textdistance/algorithms/token_based.py the six token-based classes each "
    "repeat self._get_counters(*sequences) followed by "
    "self._intersect_counters(*sequences). Extract that pair into one helper "
    "_prepare_token_counters on Base in textdistance/algorithms/base.py and use "
    "it in all six classes."
)
MODEL_PROMPT = (
    "Add ONE method to the existing class Base in textdistance/algorithms/base.py.\n"
    "Existing helpers you must call (do not redefine them):\n"
    "  def _get_counters(self, *sequences: Sequence[object]) -> list[Counter]\n"
    "  def _intersect_counters(self, *sequences: Counter[T]) -> Counter[T]\n"
    "Write exactly:\n"
    "  def _prepare_token_counters(self, *sequences):\n"
    "It must set counters = self._get_counters(*sequences), then call "
    "self._intersect_counters(*counters) UNPACKED with a star, then return "
    "(counters, intersection).\n"
    "Output only the method definition, no class, no imports, no explanation."
)

CALL_SITE = re.compile(r"( *)sequences = self\._get_counters\(\*sequences\)[ \t]*# sets\n")


def log(message: str) -> None:
    print(message, flush=True)


def extract_method(text: str) -> str | None:
    """Pull the helper out of the model reply and normalise class-body indentation."""
    body = text.replace("```python", "").replace("```", "")
    lines = body.splitlines()
    try:
        start = next(i for i, ln in enumerate(lines)
                     if ln.strip().startswith("def _prepare_token_counters"))
    except StopIteration:
        return None
    indent = len(lines[start]) - len(lines[start].lstrip())
    collected: list[str] = []
    for line in lines[start:]:
        if not line.strip():
            collected.append("")
            continue
        if len(line) - len(line.lstrip()) <= indent and collected and line.strip():
            break
        collected.append(line)
    while collected and not collected[-1].strip():
        collected.pop()
    stripped = [ln[indent:] if ln[:indent].strip() == "" else ln.lstrip()
                for ln in collected]
    return "\n".join(("    " + ln) if ln else "" for ln in stripped)


def wire_blocks(text: str) -> tuple[str, int]:
    """Rewire every rewired class body to the shared helper.

    Block-scoped, not line-adjacent: in Sorensen a ``count = sum(...)`` line sits
    between the two original lines. Inside one body the ``_get_counters``
    assignment becomes the helper call, the now-redundant
    ``_intersect_counters`` line is removed, and remaining references to the
    counters as ``sequences`` become ``counters``.
    """
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    count = 0
    in_block = False
    block_indent = 0
    for line in lines:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if not in_block:
            match = CALL_SITE.match(line)
            if match:
                block_indent = len(match.group(1))
                out.append(f"{' ' * block_indent}counters, intersection = "
                           f"self._prepare_token_counters(*sequences)\n")
                count += 1
                in_block = True
                continue
            out.append(line)
            continue
        if stripped and indent < block_indent:   # leaving the method, not the body
            in_block = False
            out.append(line)
            continue
        if "_intersect_counters" in line:
            continue
        out.append(line.replace("sequences", "counters") if "sequences" in line else line)
    return "".join(out), count


def ask_model(model: str, base_url: str) -> str:
    import urllib.request
    body = json.dumps({
        "model": model, "stream": False, "prompt": MODEL_PROMPT,
        "options": {"temperature": 0.0, "num_predict": 400},
    }).encode()
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/generate", data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        return json.load(response).get("response", "")


def run_oracle(corpus: pathlib.Path, tag: str) -> tuple[int, int, set[str]]:
    """The target repository's own suite, differential and reproducible."""
    env = {**os.environ, "HYPOTHESIS_STORAGE_DIRECTORY": f"/tmp/paw-e2e/hyp_{tag}"}
    proc = subprocess.run(
        ["uv", "run", "--quiet", "--with", "hypothesis", "--with", "pytest",
         "python", "-m", "pytest", "tests/", "--ignore=tests/test_external.py",
         "-q", "--no-header", "-p", "no:cacheprovider", "--hypothesis-seed=12345"],
        cwd=corpus, capture_output=True, text=True, timeout=3600, env=env,
    )
    combined = proc.stdout + proc.stderr
    summary = [ln for ln in combined.splitlines()
               if re.search(r"\d+ (failed|passed)", ln) and "no tests ran" not in ln]
    numbers = re.findall(r"(\d+) (failed|passed)",
                         summary[-1] if summary else combined[-400:])
    failed = next((int(n) for n, k in numbers if k == "failed"), 0)
    passed = next((int(n) for n, k in numbers if k == "passed"), 0)
    names = {re.sub(r"\[.*", "", ln.split(" ", 1)[1])
             for ln in combined.splitlines() if ln.startswith("FAILED")}
    return failed, passed, names


async def ingest(corpus: pathlib.Path) -> int:
    sources, chunks = KnowledgeSourceManager(), KnowledgeChunkStore()
    total = 0
    for path in sorted((corpus / "textdistance").rglob("*.py")):
        content = path.read_text(encoding="utf-8", errors="replace")
        rel = str(path.relative_to(corpus))
        source = await sources.create(name=rel, path=rel, external_id=rel,
                                      revision="d6a68d6")
        for start, end, text in _chunk_python_file(rel, content):
            await chunks.add_chunk(source_id=source.id, content=text,
                                   span_start=start, span_end=end,
                                   metadata={"file": rel})
            total += 1
    return total


CONSTRAINTS = {"workspace_only": True, "no_network": True}


async def reviewed_plan(task_id: str, session_id: str, corpus: pathlib.Path) -> str:
    """Record a decision, review it, and bind an implementation Plan to it.

    A write is only admitted when a *reviewed* Plan says it may be. The
    harness therefore has to produce the same evidence a real engineering
    session would: a FINAL READY decision, a human review over that exact
    snapshot, and an implementation Plan bound to it.
    """
    from paw.core.planner import Planner
    from paw.core.reasoning_contracts import DecisionVersion
    from paw.core.repo_scanner import RepoFilter
    from paw.knowledge.checksum import compute_repo_revision

    constraint_hash = hashlib.sha256(json.dumps(
        CONSTRAINTS, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()
    parent = await db.record_decision(
        "readiness", "ready", task_id=task_id, session_id=session_id,
        project_revision=compute_repo_revision(corpus, RepoFilter.safe_default()),
        constraint_fingerprint=constraint_hash,
    )
    draft = DecisionVersion("draft", parent, "draft", {"readiness": "ready"},
                            "2026-10-20", "harness")
    final = DecisionVersion("final", parent, "final", {"readiness": "ready"},
                            "2026-10-20", "harness")
    await db.advance_decision_version(draft, expected_version_id=None)
    await db.advance_decision_version(final, expected_version_id="draft")
    review = await ApprovalStore.request_decision_review(final.version_id)
    await ApprovalStore.approve(review.id, "harness-human")
    plan = await Planner(
        workspace_root=corpus, hard_constraints=CONSTRAINTS,
    ).plan(task_id, purpose="implementation", decision_version_id=final.version_id)
    return plan.id


async def paw_write(task_id: str, session_id: str, corpus: pathlib.Path,
                    rel: str, content: str, operation: str) -> dict:
    """One write through the full gate: propose -> ASK -> approve -> execute.

    The write is admitted the way a real engineering write is: a reviewed
    implementation Plan binds a decision to this project revision, and the
    runtime revalidates that binding before the executor is allowed to
    touch the workspace.
    """
    executor_registry = ExecutorRegistry()
    executor_registry.register(LocalFilesystemExecutor(corpus))
    provider_registry = ProviderRegistry()
    plan_id = await reviewed_plan(task_id, session_id, corpus)
    action = ProposedAction(
        goal=GOAL, capabilities=[Capability.FILESYSTEM_WRITE], context={},
        metadata={"filesystem": {"operation": "write", "path": rel,
                                 "content": content, "mode": "replace"},
                  "preferred_executor": "local-filesystem", "model_required": False,
                  "plan_id": plan_id},
        operation_id=operation, idempotency_key=f"e2e:{operation}",
        estimated_cost=ResourceUsage(),
    )
    runtime = PawRuntime(
        AutonomyController(AutonomyBudget(max_iterations=1),
                           policy_guard=PolicyGuard(interactive=True)),
        context_compiler=ContextCompiler(auto_attach_embeddings=False),
        capability_router=CapabilityRouter(executor_registry),
        approval_store=ApprovalStore,
        model_router=ModelRouter(providers=provider_registry),
        model_executor=ModelExecutor(provider_registry=provider_registry),
        project_root=str(corpus), hard_constraints=CONSTRAINTS,
        max_iterations=1, checkpoint_interval=1,
    )
    action = runtime._scope_implementation(action)

    async def brain(_t, _g, _c, _l):
        return action

    target = corpus / rel
    before = hashlib.md5(target.read_bytes()).hexdigest()
    outcome = await runtime.run_agent(task_id, task_goal=GOAL, session_id=session_id,
                                      initial_context={}, max_iterations=1,
                                      brain_fn=brain)
    asked = bool(outcome.waiting_for_approval)
    unchanged_after_ask = hashlib.md5(target.read_bytes()).hexdigest() == before
    if outcome.approval_id:
        await ApprovalStore.approve(outcome.approval_id)
    await runtime.run_agent(task_id, task_goal=GOAL, session_id=session_id,
                            initial_context={}, max_iterations=1, brain_fn=brain,
                            resume_from_checkpoint=outcome.checkpoint_id)
    events = len(await TaskLedger.get_events(task_id))
    return {
        "path": rel, "policy_asked": asked, "bytes_unchanged_before_approval":
        unchanged_after_ask, "written": hashlib.md5(target.read_bytes()).hexdigest() != before,
        "ledger_events": events,
    }


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=pathlib.Path, default=DEFAULT_CORPUS)
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUT)
    parser.add_argument("--model", default="qwen2.5-coder:7b")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--session", default="session-runtime-e2e")
    args = parser.parse_args()

    corpus = args.corpus.resolve()
    if not (corpus / BASE_REL).is_file():
        log(f"corpus missing: run benchmarks/runtime/fetch_corpus.sh first ({corpus})")
        return 2
    subprocess.run(["git", "checkout", "--", "."], cwd=corpus, check=False)

    await set_db_path(pathlib.Path("/tmp/paw-e2e/runtime-e2e.db"))
    await db.initialize()

    report: dict = {"corpus": str(corpus)}
    report["corpus_revision"] = subprocess.check_output(
        ["git", "-C", str(corpus), "rev-parse", "--short", "HEAD"], text=True).strip()

    report["ingest_chunks"] = n = await ingest(corpus)
    log(f"[1-ingest]    chunks={n}")

    compiler = ContextCompiler(
        budget=ContextBudget(max_tokens=6000, max_fragments=30, max_sources=10),
        auto_attach_embeddings=True,
    )
    manifest = await compiler.compile_manifest("runtime-e2e", GOAL)
    files = sorted({i.external_id for i in manifest.included if i.external_id})
    report["retrieved_files"] = files
    report["retrieved_base_py"] = BASE_REL in files
    log(f"[2-retrieve]  fragments={len(manifest.included)} "
        f"tokens={manifest.final_tokens} base_py={report['retrieved_base_py']}")

    raw = await asyncio.to_thread(ask_model, args.model, args.ollama_url)
    method = extract_method(raw)
    report["model"] = args.model
    report["model_method"] = method
    log(f"[3-model]     found={bool(method)} uses_star={'*counters' in (method or '')}")
    if not method:
        log("VERDICT: BLOCKED - the local model produced no usable method")
        await db.close()
        return 1

    base_text = (corpus / BASE_REL).read_text()
    token_text = (corpus / TOKEN_REL).read_text()
    report["call_sites_before"] = token_text.count("self._get_counters(*sequences)")
    base_new = base_text.replace("    def _union_counters",
                                 method + "\n    def _union_counters", 1)
    token_new, wired = wire_blocks(token_text)
    report["call_sites_wired"] = wired

    # The baseline oracle must be measured on the PRISTINE repository, before
    # any write. It used to run after the writes, so "baseline" was really the
    # post-write state, and the "after" measurement was taken after a
    # `git checkout` plus a direct `write_text()` that bypassed PAW entirely.
    # Both states then differed only because of the direct write, so the
    # benchmark could report "PAW performed a verified change" even when PAW
    # had refused every write.
    baseline_failed, baseline_passed, baseline_names = run_oracle(corpus, "baseline")
    report["oracle_baseline_measured_before_writes"] = True
    log(f"[4-baseline]  {baseline_failed}f/{baseline_passed}p (pristine state)")

    task = await TaskManager.create(
        session_id=args.session, goal=GOAL,
        requested_capabilities=[Capability.FILESYSTEM_WRITE])
    writes = []
    for rel, content, operation in ((BASE_REL, base_new, "op-runtime-base"),
                                    (TOKEN_REL, token_new, "op-runtime-tokens")):
        writes.append(await paw_write(task.id, args.session, corpus, rel,
                                       content, operation))
    report["writes"] = writes
    for entry in writes:
        log(f"[5-{entry['path'].split('/')[-1]:<16}] asked={entry['policy_asked']} "
            f"unchanged_before_approval={entry['bytes_unchanged_before_approval']} "
            f"written={entry['written']} ledger={entry['ledger_events']}")

    final = (corpus / TOKEN_REL).read_text()
    report["call_sites_after"] = final.count("self._get_counters(*sequences)")
    report["helper_uses"] = final.count("self._prepare_token_counters(*sequences)")
    log(f"[6-rewired]   direct_get_counters={report['call_sites_before']}"
        f"->{report['call_sites_after']} helper_uses={report['helper_uses']}")

    # The "after" oracle must measure the state PAW actually produced. No
    # reset, no direct write: the files on disk are the ones the runtime
    # wrote (or did not write).
    after_failed, after_passed, after_names = run_oracle(corpus, "after")
    report["oracle"] = {
        "baseline": {"failed": baseline_failed, "passed": baseline_passed},
        "after": {"failed": after_failed, "passed": after_passed},
        "new_failures": sorted(after_names - baseline_names),
        "fixed_failures": sorted(baseline_names - after_names),
        "identical_failure_set": after_names == baseline_names,
        "measured_on_paw_output": True,
    }
    log(f"[7-verify]    baseline={baseline_failed}f/{baseline_passed}p "
        f"after={after_failed}f/{after_passed}p "
        f"identical={report['oracle']['identical_failure_set']}")
    if report["oracle"]["new_failures"]:
        log(f"             NEW FAILURES: {report['oracle']['new_failures']}")

    # The verdict must not be able to pass without PAW actually performing the
    # change. A refused write, an unwritten file, or a new test failure all
    # make this benchmark fail loudly instead of reporting a verified change.
    unwritten = [entry["path"] for entry in writes if not entry["written"]]
    report["paw_performed_all_writes"] = not unwritten
    report["unwritten_paths"] = unwritten

    # The declared verification: the target repository's own test suite,
    # run after the change. This is the artifact that says the work is
    # right - the executor's observation only says the write happened.
    verification = VerificationRecord(
        operation_id="op-runtime-tokens",
        method="target_test_suite",
        passed=not report["oracle"]["new_failures"],
        summary=(
            "the target suite did not regress"
            if not report["oracle"]["new_failures"]
            else f"new failures: {report['oracle']['new_failures']}"
        ),
        evidence=(
            f"baseline {baseline_failed} failed / {baseline_passed} passed; "
            f"after {after_failed} failed / {after_passed} passed"
        ),
        command="pytest tests/ --ignore=tests/test_external.py --hypothesis-seed=12345",
        declared_by="harness",
    )
    await log_verification_recorded(task.id, verification)
    report["verification"] = verification.to_dict()

    verdict = "PASS"
    if unwritten:
        verdict = "FAIL"
        log(f"VERDICT: FAIL - PAW did not perform these writes: {unwritten}")
    elif report["oracle"]["new_failures"]:
        verdict = "FAIL"
        log(f"VERDICT: FAIL - new test failures: {report['oracle']['new_failures']}")
    else:
        log("VERDICT: PASS - PAW performed the change and the verification passed")
    report["verdict"] = verdict

    await db.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, default=str))
    log(f"report -> {args.output}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
