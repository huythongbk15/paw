"""Durable CLI chat vertical slice over the canonical PAW runtime."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from paw.core.approval import ApprovalRequest, ApprovalStore
from paw.core.autonomy import AutonomyBudget, AutonomyController, AutonomyProfile
from paw.core.context_compiler import ContextCompiler
from paw.core.executor import CapabilityRouter, ExecutorRegistry, MockExecutor
from paw.core.model_executor import ModelExecutor
from paw.core.model_router import ModelRouter, ProviderRegistry
from paw.core.models import (
    ApprovalStatus,
    Capability,
    ChatRole,
    ChatSessionStatus,
    ProposedAction,
    StopReason,
    TaskStatus,
)
from paw.core.policy import PolicyGuard
from paw.core.runtime import PawRuntime, RuntimeOutcome
from paw.core.session import SessionManager
from paw.core.skills import get_skill_fabric
from paw.core.storage import db
from paw.core.task import Task, TaskManager
from paw.executors.filesystem import LocalFilesystemExecutor

from .chat_inspection import (
    artifacts_projection,
    checkpoint_projection,
    explain_projection,
    ledger_projection,
    plan_projection,
    policy_projection,
    skills_projection,
)
from .chat_intents import (
    change_preview as build_change_preview,
)
from .chat_intents import (
    infer_capabilities as infer_chat_capabilities,
)
from .chat_intents import (
    parse_filesystem_intent,
)


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class ChatSessionRecord:
    session_id: str
    status: ChatSessionStatus = ChatSessionStatus.ACTIVE
    current_task_id: str | None = None
    pending_approval_id: str | None = None
    last_checkpoint_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> ChatSessionRecord:
        return cls(
            session_id=row["session_id"],
            status=ChatSessionStatus(row["status"]),
            current_task_id=row.get("current_task_id"),
            pending_approval_id=row.get("pending_approval_id"),
            last_checkpoint_id=row.get("last_checkpoint_id"),
            metadata=json.loads(row.get("metadata") or "{}"),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


@dataclass
class ChatMessage:
    id: str
    session_id: str
    role: ChatRole
    content: str
    task_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_now)

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> ChatMessage:
        return cls(
            id=row["id"],
            session_id=row["session_id"],
            task_id=row.get("task_id"),
            role=ChatRole(row["role"]),
            content=row["content"],
            metadata=json.loads(row.get("metadata") or "{}"),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def as_model_message(self) -> dict[str, str]:
        return {"role": self.role.value, "content": self.content}


@dataclass
class ChatReply:
    session_id: str
    content: str
    status: str
    task_id: str | None = None
    waiting_for_approval: bool = False
    approval_id: str | None = None
    checkpoint_id: str | None = None
    reason: str | None = None
    model: str | None = None
    executor: str | None = None
    context_compiled: bool = False
    artifacts: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ChatStateStore:
    """Durable application projection for sessions and transcripts."""

    @staticmethod
    async def create_session() -> ChatSessionRecord:
        await db.initialize()
        session = await SessionManager.create()
        record = ChatSessionRecord(session_id=session.id)
        async with db.transaction() as conn:
            await conn.execute(
                """INSERT INTO chat_sessions (
                    session_id, status, current_task_id, pending_approval_id,
                    last_checkpoint_id, metadata, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.session_id,
                    record.status.value,
                    None,
                    None,
                    None,
                    "{}",
                    record.created_at.isoformat(),
                    record.updated_at.isoformat(),
                ),
            )
        return record

    @staticmethod
    async def get_session(session_id: str) -> ChatSessionRecord | None:
        await db.initialize()
        row = await db.fetch_one(
            "SELECT * FROM chat_sessions WHERE session_id = ?",
            (session_id,),
        )
        return ChatSessionRecord.from_row(row) if row else None

    @staticmethod
    async def save_session(record: ChatSessionRecord) -> None:
        record.updated_at = _now()
        async with db.transaction() as conn:
            await conn.execute(
                """UPDATE chat_sessions SET
                    status = ?, current_task_id = ?, pending_approval_id = ?,
                    last_checkpoint_id = ?, metadata = ?, updated_at = ?
                WHERE session_id = ?""",
                (
                    record.status.value,
                    record.current_task_id,
                    record.pending_approval_id,
                    record.last_checkpoint_id,
                    json.dumps(record.metadata, ensure_ascii=False),
                    record.updated_at.isoformat(),
                    record.session_id,
                ),
            )

    @staticmethod
    async def add_message(
        session_id: str,
        role: ChatRole,
        content: str,
        *,
        task_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ChatMessage:
        message = ChatMessage(
            id=uuid.uuid4().hex[:24],
            session_id=session_id,
            task_id=task_id,
            role=role,
            content=content,
            metadata=metadata or {},
        )
        async with db.transaction() as conn:
            await conn.execute(
                """INSERT INTO chat_messages (
                    id, session_id, task_id, role, content, metadata, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    message.id,
                    message.session_id,
                    message.task_id,
                    message.role.value,
                    message.content,
                    json.dumps(message.metadata, ensure_ascii=False),
                    message.created_at.isoformat(),
                ),
            )
        return message

    @staticmethod
    async def history(session_id: str, limit: int = 100) -> list[ChatMessage]:
        await db.initialize()
        rows = await db.fetch_all(
            """SELECT * FROM chat_messages WHERE session_id = ?
            ORDER BY created_at, id LIMIT ?""",
            (session_id, limit),
        )
        return [ChatMessage.from_row(row) for row in rows]


class ChatService:
    """One coherent chat path through PAW's context, gates and runtime."""

    MAX_MODEL_MESSAGES = 32
    MAX_MODEL_CHARS = 16000

    def __init__(
        self,
        provider_mode: str = "local",
        workspace_root: str | Path | None = None,
    ):
        if provider_mode not in {"local", "auto", "ollama"}:
            raise ValueError("provider_mode must be one of: local, auto, ollama")
        self.provider_mode = provider_mode
        self.workspace_root = Path(workspace_root or Path.cwd()).resolve()
        if not self.workspace_root.is_dir():
            raise ValueError(f"workspace root is not a directory: {self.workspace_root}")
        self.session: ChatSessionRecord | None = None
        self._providers = ProviderRegistry()
        if self.provider_mode in {"auto", "ollama"}:
            from paw.providers.ollama import OllamaProvider

            self._providers.register(OllamaProvider())
        self._model_router = ModelRouter(providers=self._providers)
        self._model_executor: ModelExecutor | None = ModelExecutor(
            provider_registry=self._providers
        )
        self._executor_registry = ExecutorRegistry()
        self._executor_registry.register(LocalFilesystemExecutor(self.workspace_root))
        self._executor_registry.register(MockExecutor())
        self._capability_router = CapabilityRouter(self._executor_registry)

    async def open(self, session_id: str | None = None) -> ChatSessionRecord:
        await db.initialize()
        if session_id:
            self.session = await ChatStateStore.get_session(session_id)
            if self.session is None:
                raise ValueError(f"Unknown chat session: {session_id}")
        else:
            self.session = await ChatStateStore.create_session()
        stored_workspace = self.session.metadata.get("workspace_root")
        if stored_workspace and Path(stored_workspace).resolve() != self.workspace_root:
            raise ValueError(
                "Chat session belongs to workspace "
                f"{stored_workspace}; reopen it with --workspace {stored_workspace}"
            )
        if not stored_workspace:
            self.session.metadata["workspace_root"] = str(self.workspace_root)
            await ChatStateStore.save_session(self.session)
        return self.session

    async def close(self) -> None:
        if self._model_executor is not None:
            await self._model_executor.shutdown_all()
            self._model_executor = None

    def _require_session(self) -> ChatSessionRecord:
        if self.session is None:
            raise RuntimeError("ChatService.open() must be called first")
        return self.session

    @staticmethod
    def _parse_filesystem_intent(message: str) -> dict[str, Any] | None:
        return parse_filesystem_intent(message)

    @staticmethod
    def _change_preview(intent: dict[str, Any]) -> str | None:
        return build_change_preview(intent)

    @classmethod
    def infer_capabilities(cls, message: str) -> list[Capability]:
        """Conservative deterministic intent-to-capability projection."""
        return infer_chat_capabilities(message)

    @classmethod
    def _bounded_model_messages(cls, history: list[ChatMessage]) -> list[dict[str, str]]:
        """Keep the provider prompt bounded while retaining the newest turns."""
        selected: list[ChatMessage] = []
        chars = 0
        for item in reversed(history):
            if len(selected) >= cls.MAX_MODEL_MESSAGES:
                break
            if chars + len(item.content) > cls.MAX_MODEL_CHARS and selected:
                break
            selected.append(item)
            chars += len(item.content)
        selected.reverse()
        return [item.as_model_message() for item in selected]

    async def send(self, message: str) -> ChatReply:
        session = self._require_session()
        if session.status == ChatSessionStatus.CANCELLED:
            return ChatReply(
                session_id=session.session_id,
                content="Phiên chat đã bị hủy; hãy tạo phiên mới bằng `paw chat`.",
                status=session.status.value,
            )
        if session.pending_approval_id:
            pending = await ApprovalStore.get(session.pending_approval_id)
            if pending and pending.status in {
                ApprovalStatus.PENDING,
                ApprovalStatus.APPROVED,
            }:
                return ChatReply(
                    session_id=session.session_id,
                    task_id=pending.task_id,
                    content=(
                        f"Operation {pending.operation_id} đang chờ xử lý. "
                        "Dùng `/approve` hoặc `/resume` trước khi gửi yêu cầu mới."
                    ),
                    status="waiting_approval",
                    waiting_for_approval=True,
                    approval_id=pending.id,
                    checkpoint_id=session.last_checkpoint_id,
                )

        filesystem_intent = self._parse_filesystem_intent(message)
        capabilities = self.infer_capabilities(message)
        task = await TaskManager.create(
            session_id=session.session_id,
            goal=message,
            requested_capabilities=capabilities,
        )
        session.current_task_id = task.id
        session.pending_approval_id = None
        await ChatStateStore.save_session(session)
        await ChatStateStore.add_message(
            session.session_id,
            ChatRole.USER,
            message,
            task_id=task.id,
        )

        history = await ChatStateStore.history(session.session_id)
        action_context: dict[str, Any] = {
            "session_id": session.session_id,
            "provider_mode": self.provider_mode,
            "history_messages": len(history),
            "workspace_root": str(self.workspace_root),
        }
        action_metadata: dict[str, Any] = {
            "done": True,
            "messages": self._bounded_model_messages(history),
            "chat_session_id": session.session_id,
            "preferred_executor": "mock",
        }
        if filesystem_intent:
            target = (
                self.workspace_root / str(filesystem_intent.get("path") or ".")
            ).resolve(strict=False)
            action_context.update(
                {
                    "path": str(target),
                    "filesystem_operation": filesystem_intent["operation"],
                    "size": len(
                        str(filesystem_intent.get("content") or "").encode("utf-8")
                    ),
                }
            )
            action_metadata.update(
                {
                    "filesystem": filesystem_intent,
                    "preferred_executor": "local-filesystem",
                    "model_required": False,
                    "change_preview": self._change_preview(filesystem_intent),
                }
            )

        action = ProposedAction(
            goal=message,
            capabilities=capabilities,
            context=action_context,
            metadata=action_metadata,
            operation_id=f"chat-{task.id}",
            idempotency_key=f"chat:{task.id}",
        )
        session.metadata["last_action"] = action.to_dict()
        await ChatStateStore.save_session(session)
        return await self._run_action(task, action)

    async def _build_runtime(self) -> PawRuntime:
        if self._model_executor is None:
            raise RuntimeError("ChatService is closed")
        autonomy = AutonomyController(
            budget=AutonomyBudget.from_profile(AutonomyProfile.INTERACTIVE),
            profile=AutonomyProfile.INTERACTIVE,
            policy_guard=PolicyGuard(interactive=True),
        )
        return PawRuntime(
            autonomy,
            context_compiler=ContextCompiler(auto_attach_embeddings=False),
            model_router=self._model_router,
            model_executor=self._model_executor,
            skill_fabric=await get_skill_fabric(),
            capability_router=self._capability_router,
            approval_store=ApprovalStore,
            max_iterations=1,
            checkpoint_interval=1,
            default_role="fast",
            preferred_provider=(
                self.provider_mode if self.provider_mode in {"local", "ollama"} else None
            ),
        )

    async def _run_action(
        self,
        task: Task,
        action: ProposedAction,
        *,
        resume_from_checkpoint: str | None = None,
    ) -> ChatReply:
        session = self._require_session()
        runtime = await self._build_runtime()

        async def brain(
            _task_id: str,
            _goal: str,
            _context: dict[str, Any],
            _last_observation: Any,
        ) -> ProposedAction:
            return action

        outcome = await runtime.run_agent(
            task.id,
            task_goal=task.goal,
            session_id=session.session_id,
            initial_context=action.context,
            max_iterations=1,
            resume_from_checkpoint=resume_from_checkpoint,
            brain_fn=brain,
        )
        return await self._reply_from_outcome(task, outcome)

    async def _reply_from_outcome(self, task: Task, outcome: RuntimeOutcome) -> ChatReply:
        session = self._require_session()
        observation = outcome.last_observation
        result = observation.result if observation and isinstance(observation.result, dict) else {}
        model = result.get("model")
        executor = result.get("executor")
        artifacts = result.get("artifacts") or []
        reason = outcome.reason.value if hasattr(outcome.reason, "value") else outcome.reason

        if outcome.waiting_for_approval:
            approval_id = outcome.approval_id
            if approval_id is None:
                pending = await ApprovalStore.latest_pending(task.id)
                approval_id = pending.id if pending else None
            session.pending_approval_id = approval_id
            session.last_checkpoint_id = outcome.checkpoint_id
            await ChatStateStore.save_session(session)
            capabilities = ", ".join(cap.value for cap in task.requested_capabilities)
            pending = await ApprovalStore.get(approval_id) if approval_id else None
            operation_id = pending.operation_id if pending else task.id
            content = (
                f"Cần phê duyệt operation `{operation_id}` cho capability: {capabilities}. "
                f"Approval: `{approval_id}`. Chưa gọi model hoặc executor. "
                "Dùng `/approve` để cho phép chạy đúng operation này."
            )
            if pending:
                preview = pending.action.metadata.get("change_preview")
                if preview:
                    content = f"{content}\n\n```diff\n{preview}\n```"
            status = "waiting_approval"
        elif reason == StopReason.POLICY_DENIED.value:
            session.pending_approval_id = None
            session.last_checkpoint_id = outcome.checkpoint_id
            await ChatStateStore.save_session(session)
            content = "Policy đã từ chối operation; model và executor không được gọi."
            status = "denied"
            approval_id = None
        elif observation and observation.success:
            session.pending_approval_id = None
            session.last_checkpoint_id = outcome.checkpoint_id
            await ChatStateStore.save_session(session)
            content = str(result.get("model_response") or "").strip()
            if not content:
                # The model produced no response. Surface the model error
                # honestly instead of presenting the (possibly mock)
                # capability-executor output as if it were the assistant's answer.
                model_error = result.get("model_error")
                if model_error:
                    content = f"[model không phản hồi: {model_error}]"
                else:
                    content = str(result.get("output") or "").strip() or "Đã hoàn thành."
            status = "completed"
            approval_id = None
        else:
            session.last_checkpoint_id = outcome.checkpoint_id
            await ChatStateStore.save_session(session)
            content = observation.error if observation and observation.error else f"Đã dừng: {reason}"
            status = "failed"
            approval_id = None

        updated_task = await TaskManager.get(task.id)
        if updated_task:
            updated_task.selected_model = model
            updated_task.selected_executor = executor
            updated_task.result = result or None
            await TaskManager.update(updated_task)

        await ChatStateStore.add_message(
            session.session_id,
            ChatRole.ASSISTANT,
            content,
            task_id=task.id,
            metadata={
                "status": status,
                "reason": reason,
                "approval_id": approval_id,
                "checkpoint_id": outcome.checkpoint_id,
                "model": model,
                "executor": executor,
            },
        )
        return ChatReply(
            session_id=session.session_id,
            task_id=task.id,
            content=content,
            status=status,
            waiting_for_approval=outcome.waiting_for_approval,
            approval_id=approval_id,
            checkpoint_id=outcome.checkpoint_id,
            reason=str(reason) if reason else None,
            model=model,
            executor=executor,
            context_compiled=outcome.context_compiled,
            artifacts=artifacts,
        )

    async def approve(
        self,
        request_id: str | None = None,
        *,
        execute: bool = True,
    ) -> ChatReply:
        session = self._require_session()
        request_id = request_id or session.pending_approval_id
        if request_id is None:
            return ChatReply(
                session_id=session.session_id,
                content="Không có approval nào đang chờ.",
                status="idle",
            )
        candidate = await ApprovalStore.get(request_id)
        candidate_task = await TaskManager.get(candidate.task_id) if candidate else None
        if candidate is None or candidate_task is None or candidate_task.session_id != session.session_id:
            return ChatReply(
                session_id=session.session_id,
                content=f"Không tìm thấy approval `{request_id}` trong phiên này.",
                status="not_found",
            )
        request = await ApprovalStore.approve(request_id)
        if request is None:
            return ChatReply(
                session_id=session.session_id,
                content=f"Không tìm thấy approval `{request_id}`.",
                status="not_found",
            )
        if not execute:
            return ChatReply(
                session_id=session.session_id,
                task_id=request.task_id,
                content=f"Đã phê duyệt `{request.id}`. Dùng `/resume` để tiếp tục.",
                status=request.status.value,
                approval_id=request.id,
                checkpoint_id=session.last_checkpoint_id,
            )
        return await self.resume()

    async def resume(self) -> ChatReply:
        session = self._require_session()
        request_id = session.pending_approval_id
        request = await ApprovalStore.get(request_id) if request_id else None
        if request is None:
            return ChatReply(
                session_id=session.session_id,
                content="Không có operation bị dừng để resume.",
                status="idle",
            )
        if request.status == ApprovalStatus.PENDING:
            return ChatReply(
                session_id=session.session_id,
                task_id=request.task_id,
                content=f"Approval `{request.id}` vẫn đang chờ. Dùng `/approve` trước.",
                status="waiting_approval",
                waiting_for_approval=True,
                approval_id=request.id,
                checkpoint_id=session.last_checkpoint_id,
            )
        if request.status != ApprovalStatus.APPROVED:
            return ChatReply(
                session_id=session.session_id,
                task_id=request.task_id,
                content=f"Approval `{request.id}` có trạng thái `{request.status.value}`; không thể resume.",
                status=request.status.value,
                approval_id=request.id,
            )
        task = await TaskManager.get(request.task_id)
        if task is None:
            return ChatReply(
                session_id=session.session_id,
                content=f"Không tìm thấy task `{request.task_id}`.",
                status="not_found",
            )
        return await self._run_action(
            task,
            request.action,
            resume_from_checkpoint=session.last_checkpoint_id,
        )

    async def cancel(self) -> ChatReply:
        session = self._require_session()
        if session.pending_approval_id:
            await ApprovalStore.cancel(session.pending_approval_id)
        if session.current_task_id:
            task = await TaskManager.get(session.current_task_id)
            if task and task.status in {
                TaskStatus.PENDING,
                TaskStatus.RUNNING,
                TaskStatus.BLOCKED,
                TaskStatus.PARTIAL,
            }:
                await TaskManager.update_status(session.current_task_id, TaskStatus.CANCELLED)
        session.status = ChatSessionStatus.CANCELLED
        session.pending_approval_id = None
        await ChatStateStore.save_session(session)
        return ChatReply(
            session_id=session.session_id,
            task_id=session.current_task_id,
            content="Đã hủy phiên chat và operation đang chờ (nếu có).",
            status=session.status.value,
        )

    async def history(self, limit: int = 100) -> list[ChatMessage]:
        return await ChatStateStore.history(self._require_session().session_id, limit)

    async def status(self) -> dict[str, Any]:
        session = self._require_session()
        task = await TaskManager.get(session.current_task_id) if session.current_task_id else None
        approval: ApprovalRequest | None = None
        if session.pending_approval_id:
            approval = await ApprovalStore.get(session.pending_approval_id)
        return {
            "session_id": session.session_id,
            "status": session.status.value,
            "current_task_id": session.current_task_id,
            "task_status": task.status.value if task else None,
            "pending_approval_id": session.pending_approval_id,
            "approval_status": approval.status.value if approval else None,
            "last_checkpoint_id": session.last_checkpoint_id,
            "provider_mode": self.provider_mode,
            "workspace_root": str(self.workspace_root),
            "selected_model": task.selected_model if task else None,
            "selected_executor": task.selected_executor if task else None,
            "messages": len(await self.history()),
        }

    async def plan(self) -> dict[str, Any] | None:
        """Return the current operation proposal without hidden prompt history."""
        session = self._require_session()
        return plan_projection(session.current_task_id, session.metadata.get("last_action"))

    async def ledger(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return the current task's ordered audit events."""
        return await ledger_projection(self._require_session().current_task_id, limit)

    async def checkpoint(self) -> dict[str, Any] | None:
        """Return a bounded checkpoint summary for the current task."""
        return await checkpoint_projection(self._require_session().current_task_id)

    async def policy(self) -> dict[str, Any]:
        """Explain the latest policy verdict and durable approval state."""
        session = self._require_session()
        return await policy_projection(
            session.current_task_id,
            session.pending_approval_id,
        )

    async def skills(self) -> dict[str, Any]:
        """Explain selected skills and context compilation for the current task."""
        return await skills_projection(self._require_session().current_task_id)

    async def artifacts(self) -> list[dict[str, Any]]:
        """Return artifacts recorded in the current task result."""
        return await artifacts_projection(self._require_session().current_task_id)

    async def explain(self) -> dict[str, Any]:
        """Summarize why the latest task took its observed path."""
        session = self._require_session()
        return await explain_projection(
            session.current_task_id,
            session.metadata.get("last_action"),
        )


__all__ = [
    "ChatMessage",
    "ChatReply",
    "ChatService",
    "ChatSessionRecord",
    "ChatStateStore",
]
