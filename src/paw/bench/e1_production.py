"""Reproducible E1 context measurement on a reviewed source corpus."""
from __future__ import annotations

import argparse
import ast
import asyncio
import hashlib
import json
import subprocess
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import yaml

from paw.bench import case_manifest_from_dict
from paw.bench.integration import evaluate_measurement_metrics
from paw.bench.recall import measure_recall
from paw.bench.tokens import measure_tokens
from paw.core.context import ContextBudget, TokenEstimator
from paw.core.context_compiler import ContextCompiler
from paw.core.skills import BUILTIN_SKILLS
from paw.core.storage import db, set_db_path
from paw.knowledge.chunk import KnowledgeChunkStore
from paw.knowledge.source import KnowledgeSourceManager

DEFAULT_ROOT = Path(__file__).resolve().parents[3]


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(repo_root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo_root), *args], text=True,
    ).strip()


def _git_blob_digest(repo_root: Path, revision: str, path: str) -> str | None:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), "show", f"{revision}:{path}"],
        capture_output=True,
    )
    return hashlib.sha256(completed.stdout).hexdigest() \
        if completed.returncode == 0 else None


def _chunk_python_file(path: str, content: str) -> list[tuple[int, int, str]]:
    """Return budgetable symbol chunks, or [] for whole-file fallback.

    Large classes are represented by a small declaration chunk plus one chunk
    per direct method. This keeps both class and method evidence selectable.
    """
    del path  # reserved for a later language-aware chunker
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    lines = content.splitlines()
    chunks = []
    for node in tree.body:
        if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        end = node.end_lineno or node.lineno
        if end < node.lineno or end > len(lines):
            continue
        if isinstance(node, ast.ClassDef):
            methods = [
                child for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            if methods:
                header_end = methods[0].lineno - 1
                header = "\n".join(lines[node.lineno - 1:header_end]).rstrip()
                if header:
                    chunks.append((node.lineno, header_end, header))
                for method in methods:
                    method_end = method.end_lineno or method.lineno
                    method_text = "\n".join(lines[method.lineno - 1:method_end])
                    chunks.append(
                        (
                            method.lineno,
                            method_end,
                            f"# owner: {node.name}\n{method_text}",
                        ),
                    )
                continue
        text = "\n".join(lines[node.lineno - 1:end])
        if text.strip():
            chunks.append((node.lineno, end, text))
    return chunks


def _resolve_under(repo_root: Path, raw: str | Path) -> Path:
    path = (repo_root / raw).resolve()
    if not path.is_relative_to(repo_root.resolve()):
        raise ValueError(f"path outside repository: {raw}")
    return path


def _discover_python(repo_root: Path, roots: Sequence[str]) -> list[Path]:
    files: set[Path] = set()
    for raw in roots:
        root = _resolve_under(repo_root, raw)
        files.update(path.resolve() for path in root.rglob("*.py") if path.is_file())
    return sorted(files)


def _discover_cases(repo_root: Path, case_dir: str) -> list[Path]:
    return sorted(_resolve_under(repo_root, case_dir).glob("*.yaml"))


def _snapshot(paths: Sequence[Path], repo_root: Path) -> dict[str, str]:
    return {str(path.relative_to(repo_root)): _digest(path) for path in paths}


def _measurement_inputs(
    repo_root: Path, roots: Sequence[str], case_dir: str,
) -> tuple[list[Path], list[Path], list[Path]]:
    corpus = _discover_python(repo_root, roots)
    cases = _discover_cases(repo_root, case_dir)
    implementation = sorted((repo_root / "src" / "paw").rglob("*.py"))
    inputs = sorted({repo_root / "uv.lock", *implementation, *corpus, *cases})
    if any(not path.is_file() for path in inputs):
        raise ValueError("measurement input is missing")
    return corpus, cases, inputs


def _review_fixtures(
    repo_root: Path, case_rows: Sequence[tuple[Path, dict[str, Any], Any]],
) -> list[dict[str, Any]]:
    """Bind every reviewed fixture to an existing Git blob and current bytes."""
    reviews = []
    for case_path, raw, case in case_rows:
        project_revision = raw.get("project_revision")
        for fixture in case.fixtures:
            current = _resolve_under(repo_root, fixture.path)
            current_hash = _digest(current) if current.is_file() else None
            reviewed_hash = _git_blob_digest(
                repo_root, fixture.revision, fixture.path,
            )
            reasons = []
            if project_revision != fixture.revision:
                reasons.append("case and fixture revisions differ")
            if reviewed_hash is None:
                reasons.append("fixture does not exist at reviewed revision")
            if current_hash != reviewed_hash:
                reasons.append("current fixture bytes differ from reviewed revision")
            reviews.append({
                "case": str(case_path.relative_to(repo_root)),
                "path": fixture.path,
                "review_revision": fixture.revision,
                "reviewed_hash": reviewed_hash,
                "current_hash": current_hash,
                "fresh": not reasons,
                "reasons": reasons,
            })
    return reviews


def _measurement_decision(
    *, metric_gate: str, dirty: bool, revision_unchanged: bool,
    inputs_unchanged: bool, tree_state_unchanged: bool, fixtures_fresh: bool,
) -> tuple[str, list[str]]:
    reasons = []
    if not revision_unchanged or not inputs_unchanged or not tree_state_unchanged:
        return "BLOCKED", ["revision, measured input or tree state changed during the run"]
    if metric_gate == "FAIL":
        return "FAIL", ["at least one recall sample is below 0.50"]
    if metric_gate == "PARTIAL":
        return "PARTIAL", ["recall or median warm reduction missed its threshold"]
    if dirty:
        reasons.append("metrics passed on a dirty tree; clean-revision evidence is required")
        if not fixtures_fresh:
            reasons.append("at least one fixture differs from its reviewed revision")
        return "PARTIAL", reasons
    if not fixtures_fresh:
        return "BLOCKED", ["at least one fixture differs from its reviewed revision"]
    return "PASS", ["metrics and provenance checks passed"]


def _skill_overhead() -> int:
    estimator = TokenEstimator()
    return sum(estimator.estimate(skill.body or "") for skill in BUILTIN_SKILLS)


async def measure(
    *, repo_root: Path, roots: Sequence[str], case_dir: str,
    budget: ContextBudget,
    embedding: str = "disabled",
) -> dict:
    """Measure one immutable input snapshot; changed inputs block the result."""
    repo_root = repo_root.resolve()
    revision = _git(repo_root, "rev-parse", "HEAD")
    tree_state_before = _git(repo_root, "status", "--porcelain=v1")
    dirty = bool(tree_state_before)
    corpus, cases, owned_inputs = _measurement_inputs(repo_root, roots, case_dir)
    if not corpus:
        raise ValueError("production corpus contains no Python files")
    if not cases:
        raise ValueError("production case directory contains no YAML cases")
    before = _snapshot(owned_inputs, repo_root)
    case_rows = []
    for case_path in cases:
        raw = yaml.safe_load(case_path.read_text(encoding="utf-8"))
        case_rows.append((case_path, raw, case_manifest_from_dict(raw)))
    fixture_reviews = _review_fixtures(repo_root, case_rows)
    result = {
        "scope": "E1 measurement gate; overall E1 qualification is separate",
        "revision": revision,
        "dirty": dirty,
        "created_at": datetime.now(UTC).isoformat(),
        "corpus_roots": list(roots),
        "case_dir": case_dir,
        "case_count": len(cases),
        "corpus_file_count": len(corpus),
        "corpus_total_bytes": sum(path.stat().st_size for path in corpus),
        "configuration": {
            key: value for key, value in asdict(budget).items()
            if key != "token_estimator"
        },
        "baseline_method": "all indexed chunks plus builtin skill bodies",
        "input_hashes": before,
        "fixture_reviews": fixture_reviews,
        "samples": [],
    }
    estimator = TokenEstimator()
    baseline = _skill_overhead()
    prepared: list[tuple[Path, str, list[tuple[int, int, str]]]] = []
    for path in corpus:
        content = path.read_text(encoding="utf-8")
        chunks = _chunk_python_file(str(path.relative_to(repo_root)), content)
        baseline += sum(estimator.estimate(chunk[2]) for chunk in chunks) \
            if chunks else estimator.estimate(content)
        prepared.append((path, content, chunks))
    result["baseline_tokens"] = baseline

    with TemporaryDirectory(prefix="paw-e1-production-") as directory:
        await set_db_path(Path(directory) / "paw.db")
        await db.initialize()
        try:
            # E1-23/24/25 real measurement: optionally enable a local
            # embedding provider so semantic re-ranking is exercised on the
            # production corpus. ``local`` uses the deterministic
            # hashed-bag-of-words provider (zero external dependency);
            # ``ollama`` tries a local Ollama server and falls back to
            # lexical-only when it is unavailable.
            embedding_provider = None
            embedding_kind = "disabled"
            if embedding == "local":
                from paw.core.embeddings import LocalEmbeddingProvider
                embedding_provider = LocalEmbeddingProvider()
                embedding_kind = "local"
            elif embedding == "ollama":
                from paw.core.embeddings import try_ollama_embedding_provider
                embedding_provider = await try_ollama_embedding_provider()
                embedding_kind = "ollama" if embedding_provider else "disabled"
            result["embedding_provider"] = embedding_kind

            sources = KnowledgeSourceManager()
            chunks = KnowledgeChunkStore()
            for path, content, file_chunks in prepared:
                rel = str(path.relative_to(repo_root))
                source = await sources.create(
                    name=rel, path=rel, external_id=rel, revision=revision,
                )
                await sources.update_checksum(source.id, _digest(path))
                units = file_chunks or [(0, len(content), content)]
                for start, end, text in units:
                    await chunks.add_chunk(
                        source_id=source.id, content=text,
                        span_start=start, span_end=end,
                        metadata={"file": rel},
                    )
            compiler = ContextCompiler(
                budget=budget, auto_attach_embeddings=False,
                embedding_provider=embedding_provider,
            )
            for case_path, _raw, case in case_rows:
                for mode in ("cold", "warm"):
                    manifest = await compiler.compile_manifest(
                        task_id=case.case_id, query=case.goal, session_id=None,
                    )
                    recall = await measure_recall(
                        case, compiler=compiler, repo_root=repo_root,
                        mode=mode, manifest=manifest,
                    )
                    tokens = await measure_tokens(
                        case, compiler=compiler, repo_root=repo_root,
                        mode=mode, manifest=manifest, baseline_tokens=baseline,
                    )
                    result["samples"].append({
                        "case": str(case_path.relative_to(repo_root)),
                        "recall": asdict(recall), "tokens": asdict(tokens),
                        "included": [
                            {
                                "source": item.external_id or item.reference,
                                "score": item.relevance_score,
                                "first_line": item.content.splitlines()[0][:160]
                                if item.content else "",
                            }
                            for item in manifest.included
                        ],
                        "excluded": [
                            {
                                "source": item.external_id or item.reference,
                                "score": item.relevance_score,
                                "reason": item.metadata.get("excluded_reason"),
                                "first_line": item.content.splitlines()[0][:160]
                                if item.content else "",
                            }
                            for item in manifest.excluded
                        ],
                    })
        finally:
            await db.close()

    _after_corpus, _after_cases, after_inputs = _measurement_inputs(
        repo_root, roots, case_dir,
    )
    after = _snapshot(after_inputs, repo_root)
    result["revision_unchanged"] = _git(repo_root, "rev-parse", "HEAD") == revision
    result["inputs_unchanged"] = before == after
    result["tree_state_unchanged"] = (
        _git(repo_root, "status", "--porcelain=v1") == tree_state_before
    )
    result["fixtures_fresh"] = all(row["fresh"] for row in fixture_reviews)
    recalls = [sample["recall"]["recall"] for sample in result["samples"]]
    warm = sorted(
        sample["tokens"]["reduction"] for sample in result["samples"]
        if sample["tokens"]["mode"] == "warm"
    )
    midpoint = len(warm) // 2
    median = warm[midpoint] if len(warm) % 2 else (warm[midpoint - 1] + warm[midpoint]) / 2
    result["min_recall"] = min(recalls)
    result["median_warm_reduction"] = median
    metric_gate, metric_reasons = evaluate_measurement_metrics(recalls, warm)
    decision, reasons = _measurement_decision(
        metric_gate=metric_gate,
        dirty=dirty,
        revision_unchanged=result["revision_unchanged"],
        inputs_unchanged=result["inputs_unchanged"],
        tree_state_unchanged=result["tree_state_unchanged"],
        fixtures_fresh=result["fixtures_fresh"],
    )
    result["metric_gate"] = metric_gate
    result["metric_reasons"] = list(metric_reasons)
    result["measurement_gate"] = decision
    result["gate_reasons"] = reasons
    result["evidence_state"] = "VERIFIED" if decision == "PASS" else "OBSERVED"
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--roots", nargs="+", default=["src/paw"])
    parser.add_argument("--case-dir", default="benchmarks/e1/cases")
    parser.add_argument("--max-tokens", type=int, default=5000)
    parser.add_argument("--max-fragments", type=int, default=30)
    parser.add_argument("--max-sources", type=int, default=10)
    parser.add_argument(
        "--embedding", choices=["disabled", "local", "ollama"],
        default="disabled",
        help="Embedding provider for semantic re-ranking. "
             "'local' uses the deterministic hashed-bag-of-words provider "
             "(zero external dependency); 'ollama' tries a local Ollama server.",
    )
    args = parser.parse_args(argv)
    budget = ContextBudget(
        max_tokens=args.max_tokens, max_fragments=args.max_fragments,
        max_sources=args.max_sources,
    )
    with args.output.open("x", encoding="utf-8") as stream:
        try:
            report = asyncio.run(measure(
                repo_root=args.repo_root, roots=args.roots,
                case_dir=args.case_dir, budget=budget,
                embedding=args.embedding,
            ))
        except Exception as exc:
            json.dump({"measurement_gate": "BLOCKED", "error_type": type(exc).__name__}, stream)
            stream.write("\n")
            raise
        json.dump(report, stream, indent=2)
        stream.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
