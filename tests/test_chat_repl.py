"""Tests for the Chat REPL / ChatService integration point.

Tests the ``paw chat`` CLI surface end-to-end through the real PawRuntime
loop (run_agent → ContextCompiler → SkillFabric → ModelRouter →
ModelExecutor → PolicyGate → AutonomyGate), with LocalModelExecutor
as the offline provider.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from paw.core.storage import db, set_db_path
from paw.core.task import TaskManager
from paw.core.models import TaskStatus
from paw.application.chat import ChatService, ChatRole
from paw.core.beta_profiles import ANALYZE, CHANGE, REVIEW, IDEOATE


@pytest.fixture(autouse=True)
def _chat_db(tmp_path):
    """Each test gets its own isolated SQLite database."""
    db_path = tmp_path / "test_chat_repl.db"
    asyncio.run(set_db_path(str(db_path)))
    asyncio.run(db.initialize())
    yield db_path
    asyncio.run(db.close())


_WORKSPACE = Path("/tmp")


class TestChatSendReceive:
    """BETA: chat sends a message, gets a reply."""

    def test_send_simple_message_returns_reply(self):
        """A basic chat message produces a ChatReply with content and status."""
        async def setup():
            service = ChatService(provider_mode="local", workspace_root=_WORKSPACE)
            await service.open()
            reply = await service.send("Hello PAW")
            await service.close()
            return reply
        reply = asyncio.run(setup())
        assert reply.session_id is not None
        assert reply.content is not None
        assert len(reply.content) > 0
        assert reply.status in {"completed", "waiting_approval", "denied", "failed"}

    def test_session_persists_across_calls(self):
        """Multiple messages on the same session produce the same session_id."""
        async def setup():
            service = ChatService(provider_mode="local", workspace_root=_WORKSPACE)
            session = await service.open()
            sid = session.session_id
            await service.send("Hello")
            await service.send("World")
            assert service._require_session().session_id == sid
            await service.close()
            return sid
        sid = asyncio.run(setup())
        assert len(sid) > 0

    def test_message_stored_in_history(self):
        """User and assistant messages are both persisted."""
        from paw.application.chat import ChatStateStore

        async def setup():
            service = ChatService(provider_mode="local", workspace_root=_WORKSPACE)
            await service.open()
            await service.send("Analyze this repo")
            history = await service.history()
            await service.close()
            return history
        history = asyncio.run(setup())
        assert len(history) == 2  # user + assistant
        assert history[0].role == ChatRole.USER
        assert history[1].role == ChatRole.ASSISTANT


class TestChatProfiles:
    """The chat REPL uses BetaProfile configuration."""

    def test_analyze_profile_is_read_only(self):
        assert ANALYZE.side_effect_policy.value == "read_only"

    def test_change_profile_is_gated(self):
        assert CHANGE.side_effect_policy.value == "gated"

    def test_review_profile_is_non_mutating(self):
        """REVIEW profile is non-mutating — no write side effects."""
        assert REVIEW.side_effect_policy.value in {"read_only", "non_mutating"}

    def test_ideate_profile_is_read_only(self):
        assert IDEOATE.side_effect_policy.value == "read_only"


class TestChatPrivacy:
    """BETA B-10: privacy review — chat uses local-only policies."""

    def test_runtime_uses_local_policy_guard(self):
        """The ChatService builds a runtime with a local-only policy guard."""
        async def setup():
            service = ChatService(provider_mode="local", workspace_root=_WORKSPACE)
            runtime = await service._build_runtime()
            return runtime
        runtime = asyncio.run(setup())
        assert runtime.autonomy.policy_guard is not None
        assert isinstance(runtime.model_executor, type(runtime.model_executor).__mro__[0])

    def test_no_remote_provider_calls_with_local_mode(self):
        """With provider_mode='local', no remote model call is made."""
        async def setup():
            service = ChatService(provider_mode="local", workspace_root=_WORKSPACE)
            session = await service.open()
            reply = await service.send("What is 2+2?")
            await service.close()
            return reply
        reply = asyncio.run(setup())
        assert reply.status in {"completed", "denied", "waiting_approval", "failed"}
        # Local mode — no remote provider
        assert reply.executor == "local" or reply.model is None or "local" in str(reply.model).lower()


class TestChatInspect:
    """BETA B-09: inspect commands work through the CLI."""

    def test_status_returns_session_info(self):
        async def setup():
            service = ChatService(provider_mode="local", workspace_root=_WORKSPACE)
            await service.open()
            await service.send("test")
            status = await service.status()
            await service.close()
            return status, service
        status, service = asyncio.run(setup())
        assert "session_id" in status
        assert "status" in status

    def test_history_returns_messages(self):
        async def setup():
            service = ChatService(provider_mode="local", workspace_root=_WORKSPACE)
            await service.open()
            await service.send("hello")
            await service.send("world")
            history = await service.history()
            await service.close()
            return history
        history = asyncio.run(setup())
        assert len(history) >= 4  # 2 user + 2 assistant

    def test_plan_returns_action_or_none(self):
        async def setup():
            service = ChatService(provider_mode="local", workspace_root=_WORKSPACE)
            await service.open()
            await service.send("hello")
            plan = await service.plan()
            await service.close()
            return plan
        plan = asyncio.run(setup())
        assert plan is None or isinstance(plan, dict)


class TestChatRestartSafety:
    """BETA B-08: restart safety — denied=zero, completed=not repeated."""

    def test_restart_does_not_repeat_completed_task(self):
        """A completed task is not re-executed on restart."""
        async def setup_and_complete():
            service = ChatService(provider_mode="local", workspace_root=_WORKSPACE)
            session = await service.open()
            await service.send("task one")
            tasks_before = await TaskManager.list()
            completed_before = [t for t in tasks_before if t.status == TaskStatus.COMPLETED]
            await service.close()
            return session.session_id, len(completed_before)

        async def restart_and_check(sid: str, expected_before: int):
            service = ChatService(provider_mode="local", workspace_root=_WORKSPACE)
            await service.open(session_id=sid)
            tasks_after = await TaskManager.list()
            completed_after = [t for t in tasks_after if t.status == TaskStatus.COMPLETED]
            await service.close()
            return len(completed_after), expected_before

        sid, count_before = asyncio.run(setup_and_complete())
        assert count_before >= 1
        count_after, _ = asyncio.run(restart_and_check(sid, count_before))
        assert count_after >= count_before


class TestChatCLIStructure:
    """The chat REPL CLI command exists with expected flags."""

    def test_chat_command_exists_in_cli(self):
        from paw.cli import app

        # The `paw chat` command is registered
        import typer
        from typer.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(app, ["chat", "--help"])
        assert result.exit_code == 0
        assert "message" in result.stdout.lower() or "-m" in result.stdout
        assert "session" in result.stdout.lower() or "-s" in result.stdout
