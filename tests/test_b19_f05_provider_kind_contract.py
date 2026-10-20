"""B-19/F05: the provider name must map to a real disclosure kind.

The disclosure table is keyed by *kind* — ``local``, ``cloud_approved``,
``cloud_unapproved`` — not by provider name. The runtime used the provider
name itself as the kind::

    provider_kind = PROVIDER_LOCAL if provider_name == "ollama" else provider_name

For every real cloud provider that produces a value outside
``PROVIDER_KINDS``, so ``_refusal_reason`` returned
``unknown_provider_kind`` and every remote call refused — the class table
never actually decided anything. A second provider ("vllm", "offline") was
also not recognised as local.

This contract pins the E1-03 mapping: an on-box provider is ``local``, a
charter-admitted cloud provider is ``cloud_approved``, and everything else
is ``cloud_unapproved``. The charter-admitted cloud set is empty by
default, so today every non-local provider is ``cloud_unapproved``.
"""

from __future__ import annotations

import pytest

from paw.core.models import ModelManifest
from paw.core.privacy import (
    APPROVED_CLOUD_PROVIDERS,
    LOCAL_PROVIDER_NAMES,
    PROVIDER_CLOUD_APPROVED,
    PROVIDER_CLOUD_UNAPPROVED,
    PROVIDER_KINDS,
    PROVIDER_LOCAL,
    provider_kind_for,
)


class TestProviderKindMapping:
    @pytest.mark.parametrize("name", sorted(LOCAL_PROVIDER_NAMES))
    def test_on_box_providers_are_local(self, name):
        assert provider_kind_for(name) == PROVIDER_LOCAL

    @pytest.mark.parametrize(
        "name", ["openrouter", "openai", "dashscope", "anthropic", "together"]
    )
    def test_other_providers_are_unapproved_cloud(self, name):
        assert provider_kind_for(name) == PROVIDER_CLOUD_UNAPPROVED

    def test_every_kind_the_mapper_produces_is_known(self):
        """The whole point: the mapper may not emit an unknown kind."""
        for name in ("local", "offline", "vllm", "ollama", "openrouter", ""):
            assert provider_kind_for(name) in PROVIDER_KINDS

    def test_name_matching_is_case_and_space_insensitive(self):
        assert provider_kind_for("  Ollama ") == PROVIDER_LOCAL
        assert provider_kind_for("OLLAMA") == PROVIDER_LOCAL

    def test_approved_cloud_set_is_empty_by_default(self):
        """The E1-03 contract defers the cloud baseline, so the set is empty."""
        assert frozenset() == APPROVED_CLOUD_PROVIDERS
        assert PROVIDER_CLOUD_APPROVED not in {
            provider_kind_for(name)
            for name in ("openrouter", "openai", "dashscope")
        }

    def test_model_manifest_local_predicate_uses_the_same_set(self):
        """``ModelManifest.local`` and the mapper must not drift."""
        for name in sorted(LOCAL_PROVIDER_NAMES):
            assert ModelManifest(name="m", provider=name).local is True
            assert provider_kind_for(name) == PROVIDER_LOCAL
        for name in ("openrouter", "openai"):
            assert ModelManifest(name="m", provider=name).local is False


class TestDisclosureTableIsReachable:
    """With a real kind, the class table decides instead of the kind check."""

    def test_public_class_may_reach_an_unapproved_cloud(self):
        from paw.core.privacy import PrivacyClass, can_disclose_to_provider

        assert can_disclose_to_provider(
            PrivacyClass.PUBLIC, PROVIDER_CLOUD_UNAPPROVED
        ) is True

    def test_internal_class_may_not_reach_an_unapproved_cloud(self):
        from paw.core.privacy import PrivacyClass, can_disclose_to_provider

        assert can_disclose_to_provider(
            PrivacyClass.INTERNAL, PROVIDER_CLOUD_UNAPPROVED
        ) is False

    def test_secret_class_may_not_reach_any_cloud(self):
        from paw.core.privacy import PrivacyClass, can_disclose_to_provider

        assert can_disclose_to_provider(
            PrivacyClass.SECRET, PROVIDER_CLOUD_UNAPPROVED
        ) is False
        assert can_disclose_to_provider(
            PrivacyClass.SECRET, PROVIDER_CLOUD_APPROVED
        ) is False
        assert can_disclose_to_provider(PrivacyClass.SECRET, PROVIDER_LOCAL) is True
