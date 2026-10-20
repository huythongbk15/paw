"""B-19/F04: provider discovery must be an explicit, authorized operation.

Two implicit provider-I/O sites existed:

* ``ChatService.open()`` called ``initialize_all()``, so **starting a chat
  session** reached a provider with no operation authorized;
* ``ModelRouter.route()`` called ``ensure_providers_ready()`` and then
  ``discover_models()``, so **choosing a model** reached a provider with no
  operation authorized.

The AGENTS.md contract is explicit: *"Model Router selects only from admitted
cached manifests"*. Discovery is now an explicit operation that the runtime
performs only after Policy admits ``network.http``.

The contract pinned here:

* routing performs zero discovery and zero provider initialization;
* opening a chat session performs zero provider initialization;
* the runtime performs discovery only when Policy allows it;
* a denied discovery leaves the cached manifests in place and the run
  continues on them.
"""

from __future__ import annotations

from typing import Any

import pytest

from paw.core.autonomy import AutonomyBudget, AutonomyController
from paw.core.model_router import ModelRouter, ProviderRegistry
from paw.core.models import Capability, ModelManifest
from paw.core.policy import PolicyGuard
from paw.core.runtime import PawRuntime


async def _noop_persist(*args, **kwargs):
    """``persist_selection`` is awaited; a plain lambda is not awaitable."""
    return None


class _CountingProvider:
    """A provider that counts every I/O it is asked to do."""

    def __init__(self, name: str = "mockp", available: bool = True):
        self.name = name
        self._available = available
        self.initialize_calls = 0
        self.discover_calls = 0
        self.initialized = False
        self._models = [
            ModelManifest(
                name="mock-llama",
                provider=name,
                roles=["fast", "reasoning"],
                model_capabilities={"tool_calling": 9.0},
                cost={"compute": "low", "monetary": "free"},
                features={"resumable": True, "streaming": True},
                max_context_tokens=32000,
                latency_tier="low",
                enabled=True,
            )
        ]

    @property
    def available(self) -> bool:
        return self._available

    async def initialize(self) -> None:
        self.initialize_calls += 1
        self.initialized = True

    async def shutdown(self) -> None:
        self.initialized = False

    async def list_models(self) -> list[dict[str, Any]]:
        return [{"name": m.name} for m in self._models]

    async def get_model(self, name: str) -> dict[str, Any] | None:
        return {"name": name}

    async def discover_manifests(self):
        self.discover_calls += 1
        return list(self._models)


class _DenyGuard(PolicyGuard):
    """A guard that denies everything, so discovery must not happen."""

    async def evaluate_request(self, capabilities, context=None, task_id=None):
        class _Verdict:
            allowed = False
            verdict = "block"
            reason = "denied by test"
            stop_reason = None
            blocked = list(capabilities)
            asked = []
            details = {}

        return _Verdict()


class _AllowGuard(PolicyGuard):
    """A guard that allows everything."""

    async def evaluate_request(self, capabilities, context=None, task_id=None):
        class _Verdict:
            allowed = True
            verdict = "go"
            reason = "allowed by test"
            stop_reason = None
            blocked = []
            asked = []
            details = {}

        return _Verdict()


# --- 1. Selecting a model does no provider I/O ---------------------------


@pytest.mark.asyncio
async def test_routing_performs_no_provider_io():
    provider = _CountingProvider()
    router = ModelRouter(providers=[provider])
    router.persist_selection = _noop_persist

    selection = await router.route("t-f04-route", "goal", role="fast")

    assert provider.discover_calls == 0, "routing performed discovery"
    assert provider.initialize_calls == 0, "routing initialized a provider"
    # The provider's model was never admitted, so it cannot be selected.
    assert selection.model_name == "local-fast"


@pytest.mark.asyncio
async def test_explicit_discovery_admits_the_models():
    """The explicit operation is what admits models into the cache."""
    provider = _CountingProvider()
    router = ModelRouter(providers=[provider])
    router.persist_selection = _noop_persist

    count = await router.discover_providers()

    assert count == 1
    assert provider.discover_calls == 1
    assert provider.initialize_calls == 1
    selection = await router.route("t-f04-discover", "goal", role="fast")
    assert selection.model_name == "mock-llama"


# --- 2. Opening a session does no provider I/O ---------------------------


@pytest.mark.asyncio
async def test_opening_a_chat_session_does_no_provider_io(tmp_path):
    from paw.application.chat import ChatService
    from paw.core.storage import db, set_db_path

    await set_db_path(tmp_path / "paw.db")
    await db.initialize()

    provider = _CountingProvider()
    registry = ProviderRegistry()
    registry.register(provider)

    service = ChatService(providers=registry, workspace_root=tmp_path)
    session = await service.open()

    assert session is not None
    assert provider.initialize_calls == 0, "opening a session initialized a provider"
    assert provider.discover_calls == 0, "opening a session performed discovery"


# --- 3. The runtime admits discovery only through Policy ------------------


@pytest.mark.asyncio
async def test_runtime_refuses_discovery_when_policy_denies(tmp_path):
    """A denied discovery performs no provider I/O and the run continues."""
    from paw.core.storage import db, set_db_path

    await set_db_path(tmp_path / "paw.db")
    await db.initialize()

    provider = _CountingProvider()
    registry = ProviderRegistry()
    registry.register(provider)
    router = ModelRouter(providers=registry)
    router.persist_selection = _noop_persist

    runtime = PawRuntime(
        AutonomyController(
            budget=AutonomyBudget(max_iterations=1, max_decisions=5),
            policy_guard=_DenyGuard(),
        ),
        model_router=router,
    )

    admitted = await runtime._admit_provider_discovery("t-f04-deny")

    assert admitted is False
    assert provider.initialize_calls == 0, "a denied discovery still reached the provider"
    assert provider.discover_calls == 0


@pytest.mark.asyncio
async def test_runtime_performs_discovery_when_policy_allows(tmp_path):
    from paw.core.storage import db, set_db_path

    await set_db_path(tmp_path / "paw.db")
    await db.initialize()

    provider = _CountingProvider()
    registry = ProviderRegistry()
    registry.register(provider)
    router = ModelRouter(providers=registry)
    router.persist_selection = _noop_persist

    runtime = PawRuntime(
        AutonomyController(
            budget=AutonomyBudget(max_iterations=1, max_decisions=5),
            policy_guard=_AllowGuard(),
        ),
        model_router=router,
    )

    admitted = await runtime._admit_provider_discovery("t-f04-allow")

    assert admitted is True
    assert provider.discover_calls == 1
    assert provider.initialize_calls == 1


@pytest.mark.asyncio
async def test_discovery_is_asked_for_as_network_http(tmp_path):
    """The capability presented to Policy must be the network one."""
    from paw.core.storage import db, set_db_path

    await set_db_path(tmp_path / "paw.db")
    await db.initialize()

    asked: list[list[Capability]] = []

    class _RecordingGuard(_AllowGuard):
        async def evaluate_request(self, capabilities, context=None, task_id=None):
            asked.append(list(capabilities))
            return await super().evaluate_request(capabilities, context, task_id)

    provider = _CountingProvider()
    registry = ProviderRegistry()
    registry.register(provider)
    router = ModelRouter(providers=registry)
    router.persist_selection = _noop_persist

    runtime = PawRuntime(
        AutonomyController(
            budget=AutonomyBudget(max_iterations=1, max_decisions=5),
            policy_guard=_RecordingGuard(),
        ),
        model_router=router,
    )

    await runtime._admit_provider_discovery("t-f04-capability")

    assert asked, "Policy was never consulted about discovery"
    assert Capability.NETWORK_HTTP in asked[0]
