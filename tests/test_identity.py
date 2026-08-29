"""Tests for the Identity module (Phase 4 spec) — key/value identity store."""

from __future__ import annotations

from paw.core.identity import Identity, IdentityManager


async def test_bootstrap_seeds_defaults(temp_db):
    mgr = IdentityManager()
    await mgr.bootstrap()
    assert await mgr.get("name") == "PAW"
    assert await mgr.get("version") == "0.1.0"
    assert await mgr.get("description")
    assert await mgr.get("persona") == "precise"


async def test_get_missing_returns_default(temp_db):
    mgr = IdentityManager()
    await mgr.bootstrap()
    assert await mgr.get("nonexistent", "fallback") == "fallback"


async def test_set_get_roundtrip_json(temp_db):
    mgr = IdentityManager()
    await mgr.set("prefs", {"theme": "dark", "verbose": True})
    val = await mgr.get("prefs")
    assert isinstance(val, dict)
    assert val == {"theme": "dark", "verbose": True}


async def test_get_all(temp_db):
    mgr = IdentityManager()
    await mgr.bootstrap()
    await mgr.set("custom", "x")
    all_ids = await mgr.get_all()
    assert all_ids["name"] == "PAW"
    assert all_ids["custom"] == "x"


async def test_delete(temp_db):
    mgr = IdentityManager()
    await mgr.set("tmp", "v")
    assert await mgr.get("tmp") == "v"
    await mgr.delete("tmp")
    assert await mgr.get("tmp", None) is None


async def test_load_returns_typed_identity(temp_db):
    mgr = IdentityManager()
    await mgr.bootstrap()
    ident = await mgr.load()
    assert isinstance(ident, Identity)
    assert ident.name == "PAW"
    assert ident.version == "0.1.0"
    assert ident.persona == "precise"


async def test_overwrite_false_keeps_existing(temp_db):
    mgr = IdentityManager()
    await mgr.bootstrap()
    await mgr.set("name", "Custom")
    await mgr.bootstrap()  # overwrite=False by default -> keeps "Custom"
    assert await mgr.get("name") == "Custom"


async def test_overwrite_true_resets(temp_db):
    mgr = IdentityManager()
    await mgr.bootstrap()
    await mgr.set("name", "Custom")
    await mgr.bootstrap(overwrite=True)
    assert await mgr.get("name") == "PAW"
