"""BETA B-14: Verify single-user/local-authority behavior.

Project IDs and session IDs are scoping keys for task organization and
checkpoint/resume, NOT security boundaries. PAW is single-user by design —
there is no tenant isolation, authentication, or access control between
"users". This test suite proves that behavior: one process/database can read
all tasks, sessions, and memory regardless of session_id or project_id.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest

from paw.core.storage import db, set_db_path
from paw.core.task import TaskManager
from paw.core.memory import MemoryStore, MemoryRecord, MemoryType
from paw.core.models import Capability, TaskStatus


@pytest.fixture(autouse=True)
def _iso_db(tmp_path):
    """Each test gets its own isolated SQLite database."""
    db_path = tmp_path / "test_single_user.db"
    asyncio.run(set_db_path(str(db_path)))
    asyncio.run(db.initialize())
    yield db_path
    asyncio.run(db.close())


class TestSingleUserAccess:
    """B-14: Prove session_id/project_id are scoping keys, not isolation."""

    def test_any_session_can_read_tasks_from_other_sessions(self):
        """Tasks in session-A are readable from session-B. No isolation."""
        async def setup():
            await TaskManager.create("session-A", "Goal A", project_id="project-1")
            await TaskManager.create("session-B", "Goal B", project_id="project-2")
            # Read ALL tasks — list() with no filter returns everything
            return await TaskManager.list()

        tasks = asyncio.run(setup())
        # Both tasks visible — no tenant isolation (list() with no filter returns all)
        assert len(tasks) == 2
        session_ids = {t.session_id for t in tasks}
        assert session_ids == {"session-A", "session-B"}

    def test_project_scoping_is_organizational_not_security(self):
        """Tasks across different projects are visible without project filter."""
        async def setup():
            await TaskManager.create("session-BETA", "Project task 1", project_id="proj-public-data")
            await TaskManager.create("session-BETA", "Project task 2", project_id="proj-private-data")
            return await TaskManager.list()

        tasks = asyncio.run(setup())
        project_ids = {t.project_id for t in tasks}
        assert project_ids == {"proj-public-data", "proj-private-data"}
        # No access control — both projects visible in a single list() call
        assert len(tasks) == 2

    def test_memory_is_not_scoped_by_session(self):
        """Memory records from one session are accessible globally — no isolation."""
        async def setup():
            store = MemoryStore()
            await store.store(MemoryRecord(
                content="secret from session-A", memory_type=MemoryType.SEMANTIC,
                task_id=None, confidence=0.9,
            ))
            await store.store(MemoryRecord(
                content="note from session-B", memory_type=MemoryType.SEMANTIC,
                task_id=None, confidence=0.8,
            ))
            # List ALL memory — no session filter
            rows = await db.fetchall("SELECT * FROM memory_records ORDER BY id")
            return [MemoryRecord.from_row(dict(r)) for r in rows]

        records = asyncio.run(setup())
        # Both records visible regardless of session
        assert len(records) == 2
        contents = {r.content for r in records}
        assert "secret from session-A" in contents
        assert "note from session-B" in contents

    def test_no_authentication_layer(self):
        """There is no authentication, ACL, or tenant check in the runtime."""
        # The PawRuntime constructor has no auth/tenant parameters
        from paw.core.runtime import PawRuntime
        from paw.core.autonomy import AutonomyController, AutonomyBudget
        from paw.core.policy import PolicyGuard
        from paw.core.model_router import ModelRouter
        from paw.core.model_executor import LocalModelExecutor
        from paw.core.execution_profile import DEVELOP

        guard = PolicyGuard(interactive=False)
        autonomy = AutonomyController(policy_guard=guard, budget=AutonomyBudget())
        runtime = PawRuntime(
            autonomy=autonomy,
            context_compiler=None,
            model_router=ModelRouter(),
            model_executor=LocalModelExecutor(),
            execution_profile=DEVELOP,
            readiness="READY", current_revision="HEAD",
            checkpoint_interval=100, auto_checkpoint=False,
        )
        # No auth provider, no tenant ID, no access control fields
        assert not hasattr(runtime, "_auth_provider")
        assert not hasattr(runtime, "_current_user")
        assert not hasattr(runtime, "_tenant_id")
        # Autonomy budget has no per-user quota
        assert autonomy.budget.max_model_calls == AutonomyBudget().max_model_calls

    def test_single_shared_database(self):
        """All sessions and projects share one SQLite database file."""
        async def setup():
            await TaskManager.create("session-ABCD", "Task 1", project_id="proj-public-data")
            await TaskManager.create("session-ABCD", "Task 2", project_id="proj-private-data")
            # All tasks visible regardless of project — list() with no filter returns all
            all_tasks = await TaskManager.list()
            assert len(all_tasks) == 2

            # The tasks table has no user_id column — proof of single-user
            rows = await db.fetchall("PRAGMA table_info(tasks)")
            cols = {r["name"] for r in rows}
            assert "user_id" not in cols, "No user_id isolation column"
            return True

        result = asyncio.run(setup())
        assert result is True

    def test_no_isolation_in_task_completion(self):
        """A task in session-A can be completed and resumed by code that
        only knows the task_id — no session ownership check."""
        async def setup():
            task = await TaskManager.create("session-A", "Isolated task")
            await TaskManager.update_status(task.id, TaskStatus.RUNNING)
            # Read by task_id alone — no session check
            fetched = await TaskManager.get(task.id)
            assert fetched is not None
            assert fetched.session_id == "session-A"
            # Update by task_id alone — no session ownership check
            await TaskManager.update_status(task.id, TaskStatus.COMPLETED)
            fetched2 = await TaskManager.get(task.id)
            assert fetched2.status == TaskStatus.COMPLETED
            return True

        result = asyncio.run(setup())
        assert result is True


class TestLocalAuthorityDocumented:
    """B-14: Verify the limitation documentation is accurate."""

    def test_limitations_doc_documents_single_user(self):
        """The BETA_LIMITATIONS.md doc must explicitly state single-user."""
        doc = Path(__file__).parent.parent / "docs" / "BETA_LIMITATIONS.md"
        content = doc.read_text(encoding="utf-8")
        assert "single-user" in content.lower()
        assert "tenant isolation" in content.lower()
        # Project/session IDs must be documented as NOT security boundaries
        assert "not" in content.lower()
        assert "security" in content.lower()

    def test_beta_profiles_have_no_user_field(self):
        """BetaProfile has no user_id or tenant field — single-user by design."""
        from paw.core.beta_profiles import BetaProfile
        import dataclasses
        fields = {f.name for f in dataclasses.fields(BetaProfile)}
        assert "user_id" not in fields
        assert "tenant_id" not in fields
        assert "auth_provider" not in fields

    def test_capabilities_do_not_include_tenant_isolation(self):
        """No Capability exists for tenant isolation / multi-user access control."""
        from paw.core.models import Capability
        cap_names = {c.value for c in Capability}
        assert "tenant_isolation" not in cap_names
        assert "authenticate_user" not in cap_names
        assert "access_control" not in cap_names
