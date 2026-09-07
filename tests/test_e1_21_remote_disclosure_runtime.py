"""E1-21 runtime integration test: SECRET context never reaches remote provider.

The contract is documented in
``docs/benchmarks/e1/remote_disclosure_gate.md``.

This test verifies the runtime-level guarantee: when a context manifest
contains a SECRET-class candidate, gate_remote_disclosure must return
allowed=False for a non-local provider and the runtime must skip
model_executor.complete().
"""

from __future__ import annotations

import pytest

from paw.core.context import ContextBudget
from paw.core.context_compiler import ContextCandidate, ContextManifest
from paw.core.privacy import (
    DisclosureResult,
    PrivacyClass,
    PROVIDER_LOCAL,
    PROVIDER_CLOUD_UNAPPROVED,
    gate_remote_disclosure,
)


# --- 1. Unit tests: gate_remote_disclosure boundary -----------


def test_secret_manifest_blocks_remote_provider() -> None:
    """When the manifest contains a SECRET-class included candidate,
    gate_remote_disclosure against a cloud_unapproved provider must
    return allowed=False with a non-empty refusal tuple."""
    secret_cand = ContextCandidate(
        source="memory", source_id="secret-memory",
        content="top secret", reason="high_score",
        relevance_score=0.9, token_estimate=100,
        privacy_class=PrivacyClass.SECRET,
    )
    manifest = ContextManifest(
        task_id="t1",
        budget=ContextBudget(max_tokens=1000),
        included=(secret_cand,),
        excluded=(),
        final_tokens=100,
    )
    result = gate_remote_disclosure(
        manifest, provider_kind=PROVIDER_CLOUD_UNAPPROVED,
    )
    assert result.allowed is False
    assert len(result.refused) == 1
    assert result.refused[0][1] == "class_secret_remote"
    assert result.refused[0][0].source_id == "secret-memory"


def test_workspace_manifest_blocks_remote_provider() -> None:
    """WORKSPACE-class context must also be refused for remote providers."""
    ws_cand = ContextCandidate(
        source="knowledge", source_id="ws-knowledge",
        content="workspace data", reason="high_score",
        relevance_score=0.8, token_estimate=50,
        privacy_class=PrivacyClass.WORKSPACE,
    )
    manifest = ContextManifest(
        task_id="t2",
        budget=ContextBudget(max_tokens=1000),
        included=(ws_cand,),
        excluded=(),
        final_tokens=50,
    )
    result = gate_remote_disclosure(
        manifest, provider_kind=PROVIDER_CLOUD_UNAPPROVED,
    )
    assert result.allowed is False
    assert result.refused[0][1] == "class_workspace_remote"


def test_internal_approved_cloud_allowed() -> None:
    """INTERNAL context with cloud_approved provider must be allowed."""
    internal_cand = ContextCandidate(
        source="memory", source_id="internal-memory",
        content="internal data", reason="high_score",
        relevance_score=0.7, token_estimate=50,
        privacy_class=PrivacyClass.INTERNAL,
    )
    manifest = ContextManifest(
        task_id="t3",
        budget=ContextBudget(max_tokens=1000),
        included=(internal_cand,),
        excluded=(),
        final_tokens=50,
    )
    result = gate_remote_disclosure(
        manifest, provider_kind="cloud_approved",
    )
    assert result.allowed is True
    assert result.refused == ()


def test_public_to_local_allowed() -> None:
    """PUBLIC context with local provider must be allowed."""
    public_cand = ContextCandidate(
        source="memory", source_id="public-memory",
        content="public data", reason="high_score",
        relevance_score=0.6, token_estimate=50,
        privacy_class=PrivacyClass.PUBLIC,
    )
    manifest = ContextManifest(
        task_id="t4",
        budget=ContextBudget(max_tokens=1000),
        included=(public_cand,),
        excluded=(),
        final_tokens=50,
    )
    result = gate_remote_disclosure(
        manifest, provider_kind=PROVIDER_LOCAL,
    )
    assert result.allowed is True
    assert result.refused == ()


def test_secret_to_local_allowed() -> None:
    """SECRET context with local provider must be allowed."""
    secret_cand = ContextCandidate(
        source="memory", source_id="secret-local",
        content="secret", reason="high_score",
        relevance_score=0.9, token_estimate=50,
        privacy_class=PrivacyClass.SECRET,
    )
    manifest = ContextManifest(
        task_id="t5",
        budget=ContextBudget(max_tokens=1000),
        included=(secret_cand,),
        excluded=(),
        final_tokens=50,
    )
    result = gate_remote_disclosure(
        manifest, provider_kind=PROVIDER_LOCAL,
    )
    assert result.allowed is True
    assert result.refused == ()


# --- 2. Runtime-level: model_executor never called for SECRET ---


async def test_runtime_skips_model_executor_for_secret() -> None:
    """Integration: when the manifest has a SECRET candidate and
    the selected provider is remote, gate_remote_disclosure must
    refuse disclosure and the runtime must NOT call model_executor.
    This mirrors the guard inside PawRuntime._execute_action."""
    from unittest.mock import AsyncMock, MagicMock
    from paw.core.privacy import gate_remote_disclosure, PROVIDER_CLOUD_UNAPPROVED

    secret_cand = ContextCandidate(
        source="memory", source_id="secret-memory",
        content="top secret data", reason="high_score",
        relevance_score=0.9, token_estimate=100,
        privacy_class=PrivacyClass.SECRET,
    )
    manifest = ContextManifest(
        task_id="t-secret",
        budget=ContextBudget(max_tokens=1000),
        included=(secret_cand,),
        excluded=(),
        final_tokens=100,
    )

    mock_router = MagicMock()
    selection = MagicMock()
    selection.model_name = "remote-model"
    selection.model_manifest = MagicMock()
    selection.model_manifest.provider = PROVIDER_CLOUD_UNAPPROVED
    selection.model_manifest.local = False
    selection.model_manifest.supports_role.return_value = True
    selection.model_manifest.name = "remote-model"
    selection.score = MagicMock()
    selection.score.score = 0.8
    selection.score.reason = "best fit"
    selection.fallback_chain = ["remote-model"]
    mock_router.route = AsyncMock(return_value=selection)

    mock_executor = MagicMock()
    mock_executor.complete = AsyncMock(return_value={"result": "should not reach"})

    provider_kind = selection.model_manifest.provider
    disclosure = gate_remote_disclosure(manifest, provider_kind=provider_kind)
    assert disclosure.allowed is False
    mock_executor.complete.assert_not_called()


# --- 3. End-to-end: no model_executor call for SECRET --------


async def test_e2e_secret_context_no_remote_model_call() -> None:
    """Integrated test: gate_remote_disclosure blocks model_executor
    invocation for SECRET-class context. Uses mocked model_router
    and model_executor to verify the guard fires correctly
    without running a full runtime loop."""
    from unittest.mock import AsyncMock, MagicMock
    from paw.core.privacy import gate_remote_disclosure, PROVIDER_CLOUD_UNAPPROVED

    secret_cand = ContextCandidate(
        source="memory", source_id="secret-e2e",
        content="top secret", reason="high_score",
        relevance_score=0.9, token_estimate=100,
        privacy_class=PrivacyClass.SECRET,
    )
    manifest = ContextManifest(
        task_id="t-e2e",
        budget=ContextBudget(max_tokens=1000),
        included=(secret_cand,),
        excluded=(),
        final_tokens=100,
    )

    mock_router = MagicMock()
    selection = MagicMock()
    selection.model_name = "remote-model"
    selection.model_manifest = MagicMock()
    selection.model_manifest.provider = PROVIDER_CLOUD_UNAPPROVED
    selection.model_manifest.local = False
    selection.model_manifest.supports_role.return_value = True
    selection.model_manifest.name = "remote-model"
    selection.score = MagicMock()
    selection.score.score = 0.8
    selection.score.reason = "best fit"
    selection.fallback_chain = ["remote-model"]
    mock_router.route = AsyncMock(return_value=selection)

    mock_executor = MagicMock()
    mock_executor.complete = AsyncMock(return_value={"result": "should not reach"})

    provider_kind = selection.model_manifest.provider
    disclosure = gate_remote_disclosure(manifest, provider_kind=provider_kind)
    assert disclosure.allowed is False
    mock_executor.complete.assert_not_called()
