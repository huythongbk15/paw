"""B-19/F05: the outbound payload must be bound to the reviewed manifest.

Before this change the remote path asked only one question: *"may this
manifest go to this provider?"* — answered by ``gate_remote_disclosure``
over ``manifest.included``. The bytes that were actually sent were a
different thing entirely: ``action.metadata["messages"]``, an independent
channel the manifest never described.

That left three holes:

* a remote call with **no manifest** skipped the gate completely
  (``if manifest is not None:``), so nothing authorized it;
* a manifest belonging to **another task** was accepted;
* content the disclosure decision **refused** could still reach the
  provider through the message list — the gate proved a property of the
  manifest, not of the payload.

The contract pinned here is behavioural:

* a remote call without a manifest makes **zero provider calls** and stops;
* a foreign manifest is refused;
* a payload carrying refused content is refused;
* an oversized payload is refused;
* a clean remote payload with a valid manifest is allowed;
* a local provider is unaffected.

The fail-positive discipline applies: restoring the old
``if manifest is not None`` gate and the unbound payload fails these.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from paw.core.context import ContextBudget
from paw.core.context_compiler import ContextCandidate, ContextManifest
from paw.core.privacy import (
    DISCLOSURE_REFUSED_REASONS,
    PROVIDER_CLOUD_APPROVED,
    PROVIDER_LOCAL,
    PrivacyClass,
    bind_remote_payload,
)


SECRET_CONTENT = "top secret content that must not leak"


def _candidate(
    *,
    source_id: str = "secret-record",
    content: str = SECRET_CONTENT,
    privacy_class: PrivacyClass = PrivacyClass.SECRET,
) -> ContextCandidate:
    return ContextCandidate(
        source="memory",
        source_id=source_id,
        content=content,
        reason="high score",
        relevance_score=0.9,
        token_estimate=10,
        privacy_class=privacy_class,
    )


def _manifest(
    *,
    task_id: str = "task-f05",
    included: tuple = (),
    excluded: tuple = (),
    max_tokens: int = 1000,
) -> ContextManifest:
    return ContextManifest(
        task_id=task_id,
        budget=ContextBudget(max_tokens=max_tokens),
        included=included,
        excluded=excluded,
        final_tokens=10,
    )


def _payload(text: str) -> list[dict[str, Any]]:
    return [{"role": "user", "content": text}]


def _reasons(result) -> set[str]:
    return {reason for reason, _detail in result.refused}


# ── 1. A missing manifest refuses ───────────────────────────────────────


def test_missing_manifest_refuses():
    """A remote call with no manifest is not authorized by anything."""
    result = bind_remote_payload(
        None,
        provider_kind=PROVIDER_CLOUD_APPROVED,
        task_id="task-f05",
        payload=_payload("hello"),
    )
    assert result.allowed is False
    assert "manifest_missing" in _reasons(result)
    assert "manifest_missing" in DISCLOSURE_REFUSED_REASONS


def test_missing_manifest_still_records_the_payload_digest():
    """The refusal must still identify the bytes that were about to go."""
    result = bind_remote_payload(
        None,
        provider_kind=PROVIDER_CLOUD_APPROVED,
        task_id="task-f05",
        payload=_payload("hello"),
    )
    assert result.payload_digest
    assert result.manifest_digest == ""


# ── 2. A foreign manifest refuses ───────────────────────────────────────


def test_foreign_manifest_refuses():
    """A manifest compiled for another task does not cover this call."""
    result = bind_remote_payload(
        _manifest(task_id="other-task"),
        provider_kind=PROVIDER_CLOUD_APPROVED,
        task_id="task-f05",
        payload=_payload("hello"),
    )
    assert result.allowed is False
    assert "foreign_manifest" in _reasons(result)


def test_matching_manifest_is_not_foreign():
    result = bind_remote_payload(
        _manifest(task_id="task-f05"),
        provider_kind=PROVIDER_CLOUD_APPROVED,
        task_id="task-f05",
        payload=_payload("hello"),
    )
    assert "foreign_manifest" not in _reasons(result)


# ── 3. Refused content cannot travel through the message list ──────────


def test_payload_carrying_refused_content_refuses():
    """The binding: what the gate refused must not appear in the payload."""
    manifest = _manifest(included=(_candidate(),))
    result = bind_remote_payload(
        manifest,
        provider_kind=PROVIDER_CLOUD_APPROVED,
        task_id="task-f05",
        payload=_payload(f"please remember {SECRET_CONTENT}"),
    )
    assert result.allowed is False
    assert "payload_not_approved" in _reasons(result)


def test_clean_payload_against_a_secret_manifest_still_refuses():
    """The per-candidate refusal is unchanged by the binding."""
    manifest = _manifest(included=(_candidate(),))
    result = bind_remote_payload(
        manifest,
        provider_kind=PROVIDER_CLOUD_APPROVED,
        task_id="task-f05",
        payload=_payload("an ordinary question"),
    )
    assert result.allowed is False
    assert "class_secret_remote" in _reasons(result)


def test_excluded_secret_record_cannot_ride_the_payload():
    """A SECRET record the compiler saw but did not include is still secret."""
    manifest = _manifest(
        excluded=(_candidate(source_id="excluded-secret"),),
    )
    result = bind_remote_payload(
        manifest,
        provider_kind=PROVIDER_CLOUD_APPROVED,
        task_id="task-f05",
        payload=_payload(f"here it is: {SECRET_CONTENT}"),
    )
    assert result.allowed is False
    assert "payload_not_approved" in _reasons(result)


# ── 4. An oversized payload refuses ─────────────────────────────────────


def test_oversized_payload_refuses():
    """The payload must fit the budget the manifest was built against."""
    manifest = _manifest(max_tokens=10)
    result = bind_remote_payload(
        manifest,
        provider_kind=PROVIDER_CLOUD_APPROVED,
        task_id="task-f05",
        payload=_payload("x" * 5000),
    )
    assert result.allowed is False
    assert "payload_oversized" in _reasons(result)


# ── 5. Controls: clean remote, and local ───────────────────────────────


def test_clean_remote_payload_is_allowed():
    """A disclosable manifest with an unrelated payload is allowed."""
    manifest = _manifest(
        included=(
            _candidate(
                source_id="internal-record",
                content="ordinary internal note",
                privacy_class=PrivacyClass.INTERNAL,
            ),
        ),
    )
    result = bind_remote_payload(
        manifest,
        provider_kind=PROVIDER_CLOUD_APPROVED,
        task_id="task-f05",
        payload=_payload("what does this module do?"),
    )
    assert result.allowed is True, f"unexpected refusal: {result.refused}"
    assert result.payload_digest
    assert result.manifest_digest


def test_local_provider_is_never_refused_by_the_binding():
    """A local provider needs no disclosure decision; the binding is a
    remote-path gate and must not block on-box inference."""
    manifest = _manifest(included=(_candidate(),))
    result = bind_remote_payload(
        manifest,
        provider_kind=PROVIDER_LOCAL,
        task_id="task-f05",
        payload=_payload(SECRET_CONTENT),
    )
    # A local provider may disclose SECRET; the payload binding still
    # refuses content the gate refused, but the gate refuses nothing for
    # a local provider.
    assert result.allowed is True, f"unexpected refusal: {result.refused}"


def test_unknown_provider_kind_refuses():
    """Fail closed on a provider kind the table does not know."""
    result = bind_remote_payload(
        _manifest(),
        provider_kind="not-a-provider",
        task_id="task-f05",
        payload=_payload("hello"),
    )
    assert result.allowed is False


# ── 6. Runtime behaviour: zero provider calls ──────────────────────────


@pytest.mark.asyncio
async def test_remote_call_without_manifest_makes_zero_provider_calls(tmp_path):
    """End to end: a remote provider must not be reached without a manifest."""
    from paw.core.autonomy import AutonomyBudget, AutonomyController
    from paw.core.model_executor import ModelExecutor
    from paw.core.model_router import ModelRouter, ProviderRegistry
    from paw.core.models import Capability, ModelManifest, ProposedAction, ResourceUsage
    from paw.core.policy import PolicyGuard
    from paw.core.runtime import PawRuntime
    from paw.core.storage import db, set_db_path
    from paw.core.task import TaskManager

    db_path = tmp_path / "paw.db"
    await set_db_path(db_path)
    await db.initialize()

    calls: list[dict] = []

    class _Remote:
        name = "remote"
        initialized = True

        @property
        def available(self) -> bool:
            return True

        async def initialize(self) -> None:
            self.initialized = True

        async def shutdown(self) -> None:
            self.initialized = False

        async def list_models(self) -> list[dict]:
            return [{"name": "remote-llama"}]

        async def get_model(self, name: str):
            return {"name": name}

        async def discover_manifests(self):
            return [
                ModelManifest(
                    name="remote-llama",
                    provider="remote",
                    roles=["fast", "tools"],
                    model_capabilities={"tool_calling": 9.0},
                    cost={"compute": "low", "monetary": "free"},
                    features={"resumable": True, "streaming": True},
                    max_context_tokens=32000,
                    latency_tier="low",
                    enabled=True,
                )
            ]

        async def complete(self, request):
            calls.append(request)
            return {"response": "should never happen"}

        async def stream(self, request):
            calls.append(request)
            yield {"content": "should never happen"}

    registry = ProviderRegistry()
    registry.register(_Remote())
    router = ModelRouter(providers=registry)
    # B-19/F04: the router selects from the admitted cache, so the remote
    # model is admitted by the explicit discovery operation first.
    await router.discover_providers()

    runtime = PawRuntime(
        AutonomyController(
            budget=AutonomyBudget(max_iterations=2, max_decisions=5),
            policy_guard=PolicyGuard(interactive=False),
        ),
        model_router=router,
        model_executor=ModelExecutor(provider_registry=registry),
    )
    # No manifest: the runtime compiled nothing for this task.
    runtime._current_manifest = None

    task = await TaskManager.create(session_id="session-f05", goal="ask the remote model")

    proposed = ProposedAction(
        operation_id="op-f05-no-manifest",
        goal="ask the remote model",
        capabilities=[Capability.MODEL_INFERENCE],
        estimated_cost=ResourceUsage(),
        metadata={},
    )

    result = await runtime._execute_unit(
        task_id=task.id,
        proposed=proposed,
        iteration_index=0,
        step_fn=runtime._execute_action,
        operation_type="step",
        step_id="step-f05-1",
    )

    assert calls == [], f"the remote provider was called: {calls}"
    observation = result.observation
    assert observation is not None
    assert observation.success is False
    error = observation.error or ""
    assert "Remote disclosure refused" in error, error
    assert "manifest_missing" in error, error


@pytest.mark.asyncio
async def test_local_provider_still_runs_without_a_manifest(tmp_path):
    """Control: the binding is a remote-path gate, not a blanket block."""
    from paw.core.autonomy import AutonomyBudget, AutonomyController
    from paw.core.model_executor import ModelExecutor
    from paw.core.model_router import ModelRouter, ProviderRegistry
    from paw.core.models import Capability, ModelManifest, ProposedAction, ResourceUsage
    from paw.core.policy import PolicyGuard
    from paw.core.runtime import PawRuntime
    from paw.core.storage import db, set_db_path
    from paw.core.task import TaskManager

    db_path = tmp_path / "paw.db"
    await set_db_path(db_path)
    await db.initialize()

    calls: list[dict] = []

    class _Local:
        name = "local"
        initialized = True

        @property
        def available(self) -> bool:
            return True

        async def initialize(self) -> None:
            self.initialized = True

        async def shutdown(self) -> None:
            self.initialized = False

        async def list_models(self) -> list[dict]:
            return [{"name": "local-llama"}]

        async def get_model(self, name: str):
            return {"name": name}

        async def discover_manifests(self):
            return [
                ModelManifest(
                    name="local-llama",
                    provider="local",
                    roles=["fast", "tools"],
                    model_capabilities={"tool_calling": 9.0},
                    cost={"compute": "low", "monetary": "free"},
                    features={"resumable": True, "streaming": True},
                    max_context_tokens=32000,
                    latency_tier="low",
                    enabled=True,
                )
            ]

        async def complete(self, request):
            calls.append(request)
            return {"response": "local answer"}

        async def stream(self, request):
            calls.append(request)
            yield {"content": "local answer"}

    registry = ProviderRegistry()
    registry.register(_Local())
    router = ModelRouter(providers=registry)
    # B-19/F04: the router selects from the admitted cache.
    await router.discover_providers()

    runtime = PawRuntime(
        AutonomyController(
            budget=AutonomyBudget(max_iterations=2, max_decisions=5),
            policy_guard=PolicyGuard(interactive=False),
        ),
        model_router=router,
        model_executor=ModelExecutor(provider_registry=registry),
    )
    runtime._current_manifest = None

    task = await TaskManager.create(session_id="session-f05-local", goal="ask the local model")

    proposed = ProposedAction(
        operation_id="op-f05-local",
        goal="ask the local model",
        capabilities=[Capability.MODEL_INFERENCE],
        estimated_cost=ResourceUsage(),
        metadata={},
    )

    result = await runtime._execute_unit(
        task_id=task.id,
        proposed=proposed,
        iteration_index=0,
        step_fn=runtime._execute_action,
        operation_type="step",
        step_id="step-f05-local-1",
    )

    observation = result.observation
    assert observation is not None
    assert observation.success is True, observation.error
    assert calls, "the local provider should have been called"
