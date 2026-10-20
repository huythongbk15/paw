"""Implementation planning requires reviewed current evidence, never raw READY."""

import pytest
from unittest.mock import AsyncMock, Mock

from paw.core.approval import ApprovalStore
from paw.core.planner import Plan, Planner
from paw.core.reasoning_contracts import DecisionVersion
from paw.core.repo_filter import RepoFilter
from paw.core.storage import db
from paw.core.task import TaskManager
from paw.knowledge.checksum import compute_repo_revision


async def setup_decision(tmp_path):
    import hashlib
    import json

    root = tmp_path / "project"
    root.mkdir()
    (root / "a.py").write_text("before")
    task = await TaskManager.create("session-fixture", "review and change code")
    constraints = {"workspace_only": True, "no_network": True}
    constraint_hash = hashlib.sha256(json.dumps(
        constraints, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()
    parent = await db.record_decision(
        "readiness", "ready", task_id=task.id, session_id=task.session_id,
        project_revision=compute_repo_revision(root, RepoFilter.safe_default()),
        constraint_fingerprint=constraint_hash,
    )
    draft = DecisionVersion("draft", parent, "draft", {"readiness": "ready"}, "2026-10-06", "researcher")
    final = DecisionVersion("final", parent, "final", {"readiness": "ready"}, "2026-10-06", "researcher")
    await db.advance_decision_version(draft, expected_version_id=None)
    await db.advance_decision_version(final, expected_version_id="draft")
    return root, task, final, constraints


async def test_default_plan_is_research_and_implementation_requires_decision():
    task = await TaskManager.create("session-fixture", "analyze code")
    plan = await Planner().plan(task.id)
    assert plan.purpose == "research"
    with pytest.raises(ValueError, match="decision"):
        await Planner().plan(task.id, purpose="implementation")


async def test_reviewed_plan_reopen_and_unreviewed_refusal(tmp_path):
    root, task, final, constraints = await setup_decision(tmp_path)
    planner = Planner(workspace_root=root, hard_constraints=constraints)
    with pytest.raises(ValueError, match="review"):
        await planner.plan(task.id, purpose="implementation", decision_version_id=final.version_id)
    request = await ApprovalStore.request_decision_review(final.version_id)
    await ApprovalStore.approve(request.id, decided_by="fixture-user")
    plan = await planner.plan(task.id, purpose="implementation", decision_version_id=final.version_id)
    assert plan.decision_version_id == final.version_id
    assert plan.task_id == task.id
    assert plan.project_revision and plan.constraint_fingerprint
    await db.close()
    await db.initialize()
    loaded = await planner.get_plan(plan.id)
    assert loaded.to_dict() == plan.to_dict()


@pytest.mark.parametrize("failure", ["dirty", "constraints", "foreign", "stale", "draft", "orphan"])
async def test_invalid_decision_cannot_create_plan(tmp_path, failure):
    root, task, final, constraints = await setup_decision(tmp_path)
    request = await ApprovalStore.request_decision_review(final.version_id)
    await ApprovalStore.approve(request.id, decided_by="fixture-user")
    identity = final.version_id
    if failure == "dirty":
        (root / "a.py").write_text("changed")
    elif failure == "constraints":
        constraints = {"no_network": False}
    elif failure == "foreign":
        task = await TaskManager.create("session-fixture", "other task")
    elif failure == "stale":
        await db.advance_decision_version(
            DecisionVersion("stale", final.decision_id, "stale", final.payload, "2026-10-06", "reviewer"),
            expected_version_id=identity,
        )
    elif failure == "draft":
        identity = "draft"
    elif failure == "orphan":
        orphan = DecisionVersion("orphan", final.decision_id, "final", final.payload, "2026-10-06", "reviewer")
        await db.save_decision_version(orphan)
        identity = orphan.version_id
    with pytest.raises(ValueError):
        await Planner(workspace_root=root, hard_constraints=constraints).plan(
            task.id, purpose="implementation", decision_version_id=identity,
        )
    assert await db.fetch_one("SELECT id FROM plans") is None
    assert await db.fetch_one("SELECT id FROM task_nodes") is None


async def test_policy_denial_does_not_read_project(tmp_path, monkeypatch):
    import paw.core.planner as module

    root, task, final, constraints = await setup_decision(tmp_path)
    request = await ApprovalStore.request_decision_review(final.version_id)
    await ApprovalStore.approve(request.id, decided_by="fixture-user")
    read = Mock(side_effect=AssertionError("Policy refused: must not read"))
    monkeypatch.setattr(module, "compute_repo_revision", read)
    policy = Mock()
    policy.evaluate_request = AsyncMock(return_value=Mock(allowed=False, verdict="block"))
    planner = Planner(workspace_root=root, hard_constraints=constraints, policy_guard=policy)
    with pytest.raises(PermissionError):
        await planner.plan(task.id, purpose="implementation", decision_version_id=final.version_id)
    read.assert_not_called()
    policy.evaluate_request.assert_awaited_once()
    assert await db.fetch_one("SELECT id FROM plans") is None


async def test_direct_save_cannot_bypass_binding(tmp_path):
    root, task, final, constraints = await setup_decision(tmp_path)
    plan = Plan(id="direct-plan", task_id=task.id, session_id=task.session_id,
                goal=task.goal, purpose="implementation", decision_version_id=final.version_id)
    with pytest.raises(ValueError, match="review"):
        await Planner(workspace_root=root, hard_constraints=constraints)._save(plan)
    assert await db.fetch_one("SELECT id FROM plans") is None


async def test_pending_or_denied_review_never_authorizes_plan(tmp_path):
    root, task, final, constraints = await setup_decision(tmp_path)
    request = await ApprovalStore.request_decision_review(final.version_id)
    planner = Planner(workspace_root=root, hard_constraints=constraints)
    for deny in (False, True):
        if deny:
            await ApprovalStore.deny(request.id, decided_by="fixture-user")
        with pytest.raises(ValueError, match="review"):
            await planner.plan(task.id, purpose="implementation", decision_version_id=final.version_id)
    assert await db.fetch_one("SELECT id FROM plans") is None


async def test_exact_review_does_not_accept_other_approval(tmp_path):
    from paw.core.models import ProposedAction

    root, task, final, constraints = await setup_decision(tmp_path)
    fake = ProposedAction(operation_id=f"decision-review:{final.version_id}", goal="unrelated approval")
    request = await ApprovalStore.request(task.id, fake)
    await ApprovalStore.approve(request.id, decided_by="fixture-user")
    assert not await ApprovalStore.is_decision_reviewed(task.id, final.version_id)
    with pytest.raises(ValueError, match="review"):
        await Planner(workspace_root=root, hard_constraints=constraints).plan(
            task.id, purpose="implementation", decision_version_id=final.version_id,
        )


async def test_v6_upgrade_preserves_unbound_legacy_plan():
    # Only disposable fixture DB; recreate the prior plans layout.
    await db.write("DROP TABLE plans")
    await db.write("CREATE TABLE plans (id TEXT PRIMARY KEY, task_id TEXT, session_id TEXT NOT NULL, "
                   "goal TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, "
                   "purpose TEXT NOT NULL DEFAULT 'implementation', effect_constraints TEXT NOT NULL DEFAULT '[]')")
    await db.write("INSERT INTO plans (id, task_id, session_id, goal, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                   ("legacy-plan", "legacy-task", "legacy-session", "old goal", "2026-10-06", "2026-10-06"))
    await db.write("PRAGMA user_version = 6")
    await db.close()
    await db.initialize()
    plan = await Planner().get_plan("legacy-plan")
    assert plan.purpose == "implementation"
    assert plan.decision_version_id == ""
    assert plan.project_revision == plan.constraint_fingerprint == ""
    assert plan.goal == "old goal"
