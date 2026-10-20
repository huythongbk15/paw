"""Personal skill versioning: a version is a version, not a name.

The skill registry had three defects that made "learn a personal skill,
then roll back safely" impossible rather than merely untested:

* the in-memory index was keyed by **name**, so a candidate with the same
  name replaced the manifest that was there - a prior version was
  unreachable;
* persistence used the **name as the row id** with ``INSERT OR REPLACE``,
  so saving a new version destroyed the old row;
* ``rollback_skill`` searched that same one-entry-per-name index, so it
  could never find a different version: rolling back to a prior version
  was structurally impossible.

And two more that made an approval weaker than it looked:

* ``review_skill`` and ``approve_skill`` bound only a **name** - an
  approval could be carried over to different content;
* neither required a **replay**. A skill is executable text; reading it
  is not running it.

The contract pinned here:

* a new version is a new row, and the prior version survives;
* review and approval are bound to the exact version and content hash;
* a failed, missing or negative replay cannot activate a skill;
* changed content invalidates the approval;
* rollback finds a *prior* version, and it survives a reopen.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from paw.core.models import SkillReplayEvidence, SkillState
from paw.core.skills import SkillFabric, SkillManifest
from paw.core.storage import db, set_db_path


def _manifest(name: str, version: str, body: str) -> SkillManifest:
    return SkillManifest(
        name=name,
        version=version,
        skill_version=version,
        description=f"{name} v{version}",
        trigger=f"do {name}",
        body=body,
        capabilities=[],
    )


@pytest.fixture(autouse=True)
async def _db(tmp_path: Path):
    await set_db_path(tmp_path / "paw.db")
    await db.initialize()
    yield
    await db.close()


async def _fabric(tmp_path: Path) -> SkillFabric:
    fabric = SkillFabric(tmp_path / "skills")
    await fabric.initialize()
    return fabric


# --- Versions are rows ----------------------------------------------------


async def test_a_new_version_does_not_destroy_the_prior_one(tmp_path):
    """Two versions of one skill are two rows."""
    fabric = await _fabric(tmp_path)

    first = _manifest("helper", "1.0.0", "print('one')")
    await fabric.submit_candidate(first)
    second = _manifest("helper", "2.0.0", "print('two')")
    await fabric.submit_candidate(second)

    rows = await db.fetchall("SELECT id, name, version FROM skills WHERE name = ?", ("helper",))
    assert len(rows) == 2, f"expected 2 version rows, got {len(rows)}"
    assert {r["version"] for r in rows} == {"1.0.0", "2.0.0"}

    # Both versions are reachable by exact version.
    assert fabric.get_manifest_version("helper", "1.0.0") is not None
    assert fabric.get_manifest_version("helper", "2.0.0") is not None
    # And the current one is the latest.
    assert fabric.get_manifest("helper").skill_version == "2.0.0"


async def test_the_versions_survive_a_reopen(tmp_path):
    """An approved prior version is still there after a restart."""
    fabric = await _fabric(tmp_path)
    await fabric.submit_candidate(_manifest("helper", "1.0.0", "one"))
    await fabric.submit_candidate(_manifest("helper", "2.0.0", "two"))

    reopened = SkillFabric(tmp_path / "skills")
    await reopened.initialize()

    versions = {m.skill_version for m in reopened.list_versions("helper")}
    assert versions == {"1.0.0", "2.0.0"}


# --- Review and approval are bound ----------------------------------------


async def test_review_requires_replay_evidence(tmp_path):
    """A skill that was not replayed cannot be reviewed."""
    fabric = await _fabric(tmp_path)
    await fabric.submit_candidate(_manifest("helper", "1.0.0", "one"))

    assert await fabric.review_skill(
        "helper", "reviewer", "diff", "safe", "effect",
    ) is False, "a review without replay evidence was accepted"

    assert await fabric.review_skill(
        "helper", "reviewer", "diff", "safe", "effect",
        replay=SkillReplayEvidence(ok=False, detail="it crashed"),
    ) is False, "a review with a failed replay was accepted"

    assert await fabric.review_skill(
        "helper", "reviewer", "diff", "safe", "effect",
        replay=SkillReplayEvidence(ok=True, detail="ran clean"),
    ) is True


async def test_approval_requires_replay_evidence(tmp_path):
    """A skill that was not replayed cannot be activated."""
    fabric = await _fabric(tmp_path)
    await fabric.submit_candidate(_manifest("helper", "1.0.0", "one"))
    await fabric.review_skill(
        "helper", "reviewer", "diff", "safe", "effect",
        replay=SkillReplayEvidence(ok=True),
    )

    assert await fabric.approve_skill("helper", "approver") is False
    assert await fabric.approve_skill(
        "helper", "approver", replay=SkillReplayEvidence(ok=False, detail="crash"),
    ) is False
    assert await fabric.approve_skill(
        "helper", "approver", replay=SkillReplayEvidence(ok=True),
    ) is True
    assert fabric.get_manifest("helper").state == SkillState.ACTIVE


async def test_changed_content_invalidates_the_approval(tmp_path):
    """The approval covers a content hash, not a name."""
    fabric = await _fabric(tmp_path)
    await fabric.submit_candidate(_manifest("helper", "1.0.0", "one"))
    await fabric.review_skill(
        "helper", "reviewer", "diff", "safe", "effect",
        replay=SkillReplayEvidence(ok=True),
    )
    assert await fabric.approve_skill(
        "helper", "approver", replay=SkillReplayEvidence(ok=True),
    ) is True

    # The body changes after the approval.
    manifest = fabric.get_manifest("helper")
    manifest.body = "print('something else entirely')"

    # A new candidate of the same version is refused: the approval
    # covered a different content hash.
    changed = _manifest("helper", "1.0.0", "print('something else entirely')")
    await fabric.submit_candidate(changed)
    assert await fabric.approve_skill(
        "helper", "approver", version="1.0.0", replay=SkillReplayEvidence(ok=True),
    ) is False, "an approval survived a content change"


async def test_the_approval_is_bound_to_one_version(tmp_path):
    """Approving a version does not approve a different one."""
    fabric = await _fabric(tmp_path)
    await fabric.submit_candidate(_manifest("helper", "1.0.0", "one"))
    await fabric.submit_candidate(_manifest("helper", "2.0.0", "two"))

    # Review and approve exactly 1.0.0.
    assert await fabric.review_skill(
        "helper", "reviewer", "diff", "safe", "effect", version="1.0.0",
        replay=SkillReplayEvidence(ok=True),
    ) is True
    assert await fabric.approve_skill(
        "helper", "approver", version="1.0.0", replay=SkillReplayEvidence(ok=True),
    ) is True

    # 2.0.0 is still a candidate: it was never reviewed.
    assert fabric.get_manifest_version("helper", "2.0.0").state == SkillState.CANDIDATE


# --- Rollback -------------------------------------------------------------


async def test_rollback_finds_a_prior_version(tmp_path):
    """The prior version is reachable, and becomes current again."""
    fabric = await _fabric(tmp_path)
    await fabric.submit_candidate(_manifest("helper", "1.0.0", "one"))
    await fabric.review_skill(
        "helper", "reviewer", "diff", "safe", "effect", version="1.0.0",
        replay=SkillReplayEvidence(ok=True),
    )
    assert await fabric.approve_skill(
        "helper", "approver", version="1.0.0", replay=SkillReplayEvidence(ok=True),
    ) is True

    # A newer version is approved, superseding 1.0.0.
    await fabric.submit_candidate(_manifest("helper", "2.0.0", "two"))
    await fabric.review_skill(
        "helper", "reviewer", "diff", "safe", "effect", version="2.0.0",
        replay=SkillReplayEvidence(ok=True),
    )
    assert await fabric.approve_skill(
        "helper", "approver", version="2.0.0", replay=SkillReplayEvidence(ok=True),
    ) is True
    assert fabric.get_manifest("helper").skill_version == "2.0.0"
    assert fabric.get_manifest_version("helper", "1.0.0").state == SkillState.SUPERSEDED

    # Roll back to the prior version.
    assert await fabric.rollback_skill("helper", "1.0.0") is True
    assert fabric.get_manifest("helper").skill_version == "1.0.0"
    assert fabric.get_manifest("helper").state == SkillState.ACTIVE
    assert fabric.get_manifest_version("helper", "2.0.0").state == SkillState.SUPERSEDED


async def test_rollback_without_a_target_finds_the_prior_version(tmp_path):
    """The implicit rollback finds the prior version on its own."""
    fabric = await _fabric(tmp_path)
    await fabric.submit_candidate(_manifest("helper", "1.0.0", "one"))
    await fabric.review_skill(
        "helper", "reviewer", "diff", "safe", "effect", version="1.0.0",
        replay=SkillReplayEvidence(ok=True),
    )
    await fabric.approve_skill(
        "helper", "approver", version="1.0.0", replay=SkillReplayEvidence(ok=True),
    )
    await fabric.submit_candidate(_manifest("helper", "2.0.0", "two"))
    await fabric.review_skill(
        "helper", "reviewer", "diff", "safe", "effect", version="2.0.0",
        replay=SkillReplayEvidence(ok=True),
    )
    await fabric.approve_skill(
        "helper", "approver", version="2.0.0", replay=SkillReplayEvidence(ok=True),
    )

    assert await fabric.rollback_skill("helper") is True
    assert fabric.get_manifest("helper").skill_version == "1.0.0"


async def test_rollback_survives_a_reopen(tmp_path):
    """The rolled-back version is still the current one after a restart."""
    fabric = await _fabric(tmp_path)
    await fabric.submit_candidate(_manifest("helper", "1.0.0", "one"))
    await fabric.review_skill(
        "helper", "reviewer", "diff", "safe", "effect", version="1.0.0",
        replay=SkillReplayEvidence(ok=True),
    )
    await fabric.approve_skill(
        "helper", "approver", version="1.0.0", replay=SkillReplayEvidence(ok=True),
    )
    await fabric.submit_candidate(_manifest("helper", "2.0.0", "two"))
    await fabric.review_skill(
        "helper", "reviewer", "diff", "safe", "effect", version="2.0.0",
        replay=SkillReplayEvidence(ok=True),
    )
    await fabric.approve_skill(
        "helper", "approver", version="2.0.0", replay=SkillReplayEvidence(ok=True),
    )
    assert await fabric.rollback_skill("helper", "1.0.0") is True

    reopened = SkillFabric(tmp_path / "skills")
    await reopened.initialize()
    assert reopened.get_manifest("helper").skill_version == "1.0.0"
    assert reopened.get_manifest("helper").state == SkillState.ACTIVE
    assert {
        m.skill_version for m in reopened.list_versions("helper")
    } == {"1.0.0", "2.0.0"}


async def test_rollback_to_an_unknown_version_is_refused(tmp_path):
    """A near-miss is not a match."""
    fabric = await _fabric(tmp_path)
    await fabric.submit_candidate(_manifest("helper", "1.0.0", "one"))
    await fabric.review_skill(
        "helper", "reviewer", "diff", "safe", "effect", version="1.0.0",
        replay=SkillReplayEvidence(ok=True),
    )
    await fabric.approve_skill(
        "helper", "approver", version="1.0.0", replay=SkillReplayEvidence(ok=True),
    )
    assert await fabric.rollback_skill("helper", "9.9.9") is False
    assert await fabric.rollback_skill("helper", "1.0.0") is False, (
        "a rollback to the current version is not a rollback"
    )
