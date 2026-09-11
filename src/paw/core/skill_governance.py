"""
PAW Core — Skill Governance (E3)

Trace-to-candidate generation, redaction, duplicate detection,
approval workflow, and replay safety for personal skills.

E3 contract: every skill candidate must be traceable to verified E0-E2
traces, must preserve research/decision/implementation/verification links,
and only ACTIVE (reviewed + approved) skills may execute.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .logging import get_logger
from .models import SkillState
from .skills import SkillFabric, SkillManifest
from .storage import db

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Redaction (E3-10)
# ---------------------------------------------------------------------------

# Patterns that must be redacted from any candidate payload before persistence
REDACTION_PATTERNS = [
    # API keys / secrets (key=value or key:value)
    (re.compile(r'(?i)(api[_-]?key|secret|token|password|passwd|pwd)\s*[=:]\s*["\']?([^"\'\s,]+)'),
     r'\1=REDACTED'),
    # Bearer tokens
    (re.compile(r'(?i)(Bearer\s+)[A-Za-z0-9\-._~+/]+=*'),
     r'\1REDACTED'),
    # AWS-style keys
    (re.compile(r'(?i)(aws[_-]?(?:access[_-]?key|secret[_-]?key))\s*[=:]\s*["\']?([A-Za-z0-9/+=]{40})'),
     r'\1=REDACTED'),
    # Private paths (absolute paths starting with /home, /root, /etc/var/lib)
    (re.compile(r'(/home/|/root/|/var/lib/|/etc/)([A-Za-z0-9/_.-]+)'),
     r'\1[REDACTED]'),
    # Email addresses
    (re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+\.\w+'), '[REDACTED_EMAIL]'),
]

# Private payload keys that must be stripped
PRIVATE_KEYS = frozenset({
    "password", "secret", "token", "api_key", "apikey",
    "private_key", "access_token", "refresh_token",
})


def redact_payload(text: str) -> str:
    """Redact secrets and private paths from a text payload (E3-10)."""
    result = str(text)
    for pattern, replacement in REDACTION_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def redact_dict(d: dict[str, Any]) -> dict[str, Any]:
    """Recursively redact private keys from a dict (E3-10)."""
    if not isinstance(d, dict):
        return d
    cleaned = {}
    for k, v in d.items():
        if k.lower() in PRIVATE_KEYS:
            cleaned[k] = "[REDACTED]"
        elif isinstance(v, str):
            cleaned[k] = redact_payload(v)
        elif isinstance(v, dict):
            cleaned[k] = redact_dict(v)
        elif isinstance(v, list):
            cleaned[k] = [
                redact_dict(i) if isinstance(i, dict)
                else redact_payload(i) if isinstance(i, str)
                else i
                for i in v
            ]
        else:
            cleaned[k] = v
    return cleaned


# ---------------------------------------------------------------------------
# Candidate trace links (E3-09, E3-24)
# ---------------------------------------------------------------------------

@dataclass
class TraceLink:
    """A link from a skill candidate to its source trace (E3-24)."""
    trace_id: str
    task_id: ID
    event_types: list[str]
    source_snippets: list[str]  # redacted snippets
    created_at: str


@dataclass
class CandidateDraft:
    """A deterministic skill candidate draft from a trace (E3-09)."""
    name: str
    skill_version: str
    trigger: str
    description: str
    body: str
    category: str
    capabilities: list[str]
    risk: str
    allowed_tools: list[str]
    non_applicable_when: list[str]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    success_criteria: list[str]
    failure_criteria: list[str]
    expected_effect: str
    trace_links: list[TraceLink]
    source_hash: str  # SHA-256 of the original trace (proves determinism)
    draft_hash: str  # SHA-256 of the candidate content

    def to_manifest(self) -> SkillManifest:
        """Convert to a SkillManifest in CANDIDATE state."""
        from .models import Capability, SkillRisk
        caps = [Capability(c) for c in self.capabilities if c]
        return SkillManifest(
            name=self.name,
            version=self.skill_version,
            description=self.description,
            category=self.category,
            capabilities=caps,
            risk=SkillRisk(self.risk),
            trigger=self.trigger,
            body=self.body,
            source="candidate",
            state=SkillState.CANDIDATE,
            skill_version=self.skill_version,
            allowed_tools=self.allowed_tools,
            non_applicable_when=self.non_applicable_when,
            input_schema=self.input_schema,
            output_schema=self.output_schema,
            success_criteria=self.success_criteria,
            failure_criteria=self.failure_criteria,
            expected_effect=self.expected_effect,
        )


# Re-export ID from models
from .models import ID  # noqa: E402

# ---------------------------------------------------------------------------
# Trace-to-candidate generation (E3-09)
# ---------------------------------------------------------------------------

async def extract_task_traces(task_id: str, max_events: int = 500) -> list[dict[str, Any]]:
    """Extract all ledger events for a task, in order (E3-09)."""
    rows = await db.fetchall(
        "SELECT * FROM task_events WHERE task_id = ? ORDER BY created_at ASC LIMIT ?",
        [task_id, max_events],
    )
    return [dict(r) for r in rows]


def _event_payload(row: dict) -> dict[str, Any]:
    raw = row.get("payload")
    if raw:
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _classify_workflow(events: list[dict[str, Any]]) -> tuple[str, list[str]] | None:
    """Classify a trace into a workflow type + list of relevant event types.

    Returns (workflow_name, event_type_list) or None if not classifiable.

    A 'repeated workflow' is defined as a sequence of events that starts with
    a task creation and ends with a task completed/failed, containing at
    least one step executed and one model/context interaction.
    """
    if not events:
        return None

    types = [e.get("event_type", "") for e in events]

    # Must have a start and end
    has_start = any(t.startswith("task_created") or t.startswith("execution_started") for t in types)
    has_end = any("completed" in t or "failed" in t for t in types)
    if not has_start or not has_end:
        return None

    # Must have at least one step + one model/context interaction
    has_step = any("step" in t for t in types)
    has_model = any("model" in t for t in types)
    has_context = any("context" in t for t in types)
    if not (has_step and (has_model or has_context)):
        return None

    # Classify based on dominant activity
    if has_model and "model_selected" in types:
        workflow_name = "model-driven-task"
    elif has_context and "context_built" in types:
        workflow_name = "context-driven-task"
    elif "skill_selected" in types:
        workflow_name = "skill-augmented-task"
    else:
        workflow_name = "generic-workflow"

    return workflow_name, types


async def find_repeated_workflows(
    *,
    min_repeats: int = 2,
    limit: int = 50,
) -> list[tuple[str, list[str]]]:
    """Find workflow patterns that repeat across tasks (E3-08).

    Returns list of (workflow_name, task_ids) for workflows that appear
    at least min_repeats times in the ledger.
    """
    # Get all task IDs
    tasks = await db.fetchall(
        "SELECT DISTINCT task_id FROM task_events WHERE task_id IS NOT NULL"
    )
    task_ids = [r["task_id"] for r in tasks]

    workflow_map: dict[str, list[str]] = {}
    for tid in task_ids[:limit]:
        events = await extract_task_traces(tid)
        classified = _classify_workflow(events)
        if classified:
            workflow_name, _ = classified
            workflow_map.setdefault(workflow_name, []).append(tid)

    # Return only workflows that repeat
    return [(name, ids) for name, ids in workflow_map.items() if len(ids) >= min_repeats]


async def generate_candidate_draft(
    task_id: str,
    workflow_name: str,
    *,
    name_override: str | None = None,
) -> CandidateDraft:
    """Create a deterministic trace-to-candidate draft with source links (E3-09).

    The draft is deterministic: the same trace produces the same CandidateDraft
    (same draft_hash). Redaction is applied before any persistence.
    """
    events = await extract_task_traces(task_id)

    # Build trace links with redacted snippets
    trace_links: list[TraceLink] = []
    event_type_set: set[str] = set()

    for ev in events:
        et = ev.get("event_type", "")
        event_type_set.add(et)
        payload = _event_payload(ev)
        snippet = _redact_for_link(payload)
        trace_links.append(TraceLink(
            trace_id=f"{task_id}:ev{ev.get('id', '?')}",
            task_id=task_id,
            event_types=[et],
            source_snippets=[snippet] if snippet else [],
            created_at=ev.get("created_at", ""),
        ))

    # Compute source hash (SHA-256 of raw trace, deterministically serialized)
    raw_trace = json.dumps(events, sort_keys=True, default=str)
    source_hash = hashlib.sha256(raw_trace.encode()).hexdigest()

    # Build candidate content deterministically from trace
    # The trigger is derived from the task's query
    task_query = ""
    for ev in events:
        if ev.get("event_type", "").startswith("task_created"):
            task_query = str(_event_payload(ev).get("query", ""))
            break

    # The trigger: use the query or derived keywords
    trigger = name_override or _derive_trigger(workflow_name, task_query)

    # The body: derive from the trace
    body = _derive_body(workflow_name, events)

    # Build the full candidate
    name = name_override or _derive_name(workflow_name, task_id)
    description = f"Personal skill for {workflow_name} pattern.\nDerived from trace {task_id}."

    # Allowed tools: extract from executor/tool calls in the trace
    allowed_tools = _extract_allowed_tools(events)

    # Non-applicable conditions: derive from negative outcomes in the trace
    non_applicable = _derive_non_applicable(events)

    # Schemas: basic inference
    input_schema = {"type": "object", "properties": {"query": {"type": "string"}}}
    output_schema = {"type": "object", "properties": {"result": {"type": "string"}}}

    # Success/failure criteria
    success_criteria, failure_criteria = _derive_criteria(events)

    expected_effect = f"Reproduce the {workflow_name} workflow from trace {task_id}."

    draft = CandidateDraft(
        name=name,
        skill_version="1.0.0",
        trigger=trigger,
        description=description,
        body=body,
        category=workflow_name,
        capabilities=[],
        risk="low",
        allowed_tools=allowed_tools,
        non_applicable_when=non_applicable,
        input_schema=input_schema,
        output_schema=output_schema,
        success_criteria=success_criteria,
        failure_criteria=failure_criteria,
        expected_effect=expected_effect,
        trace_links=trace_links,
        source_hash=source_hash,
        draft_hash="",
    )

    # Compute draft_hash AFTER all fields are set
    draft_dict = {
        "name": draft.name,
        "skill_version": draft.skill_version,
        "trigger": draft.trigger,
        "description": draft.description,
        "body": draft.body,
        "category": draft.category,
        "capabilities": draft.capabilities,
        "risk": draft.risk,
        "allowed_tools": draft.allowed_tools,
        "non_applicable_when": draft.non_applicable_when,
        "input_schema": draft.input_schema,
        "output_schema": draft.output_schema,
        "success_criteria": draft.success_criteria,
        "failure_criteria": draft.failure_criteria,
        "expected_effect": draft.expected_effect,
        "source_hash": draft.source_hash,
    }
    draft.draft_hash = hashlib.sha256(
        json.dumps(draft_dict, sort_keys=True, default=str).encode()
    ).hexdigest()

    return draft


def _redact_for_link(payload: dict) -> str:
    """Create a redacted snippet from a payload for trace links (E3-10)."""
    redacted = redact_dict(payload)
    # Take key fields only
    keys_to_include = ["decision", "model_name", "capabilities", "reason", "success",
                       "query", "result", "error", "outcome"]
    snippet_parts = []
    for k in keys_to_include:
        if k in redacted:
            snippet_parts.append(f"{k}={redacted[k]}")
    return "; ".join(snippet_parts)


def _derive_trigger(workflow_name: str, task_query: str) -> str:
    """Derive a trigger phrase from the workflow and query."""
    keywords = []
    for word in task_query.lower().split():
        word = word.strip(".,!?;:\"'()[]{}")
        if word and len(word) > 3 and word not in ("what", "how", "when", "where", "why", "the", "this"):
            keywords.append(word)
    if keywords:
        return keywords[0]
    return workflow_name


def _derive_name(workflow_name: str, task_id: str) -> str:
    """Derive a skill name from workflow type and task ID."""
    safe_id = re.sub(r'[^a-zA-Z0-9_-]', '', task_id[:8])
    return f"auto-{workflow_name}-{safe_id}"


def _derive_body(workflow_name: str, events: list[dict]) -> str:
    """Derive a skill body from the workflow trace."""
    # Extract key events to form the body
    steps = []
    for ev in events:
        et = ev.get("event_type", "")
        payload = _event_payload(ev)
        if et == "step_executed" or et == "step_completed":
            action = payload.get("action", payload.get("operation", ""))
            result = payload.get("result", "")
            if action:
                steps.append(f"Step: {redact_payload(str(action))}")
                if result:
                    steps.append(f"Result: {redact_payload(str(result))[:200]}")
        elif et == "model_selected":
            model = payload.get("model_name", "local")
            steps.append(f"Model: {redact_payload(str(model))}")
        elif et == "context_built" or et == "context_compiled":
            tokens = payload.get("total_tokens", 0)
            steps.append(f"Context built with {tokens} tokens")
        elif et == "policy_checked":
            decision = payload.get("decision", "")
            steps.append(f"Policy: {redact_payload(str(decision))}")

    body = f"# Auto-derived Skill: {workflow_name}\n\n"
    body += "## Workflow Pattern\n\n"
    body += "This skill was derived from an E0-E2 verified trace.\n\n"
    body += "## Execution Steps\n\n"
    body += "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps[:20]))
    body += "\n\n## Notes\n\n"
    body += "- Source trace: see trace_links for full event log\n"
    body += "- Redacted for secrets and private paths before persistence\n"
    return body


def _extract_allowed_tools(events: list[dict]) -> list[str]:
    """Extract tool names used in the trace."""
    tools = set()
    for ev in events:
        payload = _event_payload(ev)
        et = ev.get("event_type", "")
        if et == "tool_called":
            tool = payload.get("tool_name", payload.get("tool", ""))
            if tool:
                tools.add(tool)
        # Also check step payloads
        for val in payload.values():
            if isinstance(val, str) and val.startswith("paw.tools"):
                tools.add(val)
    return sorted(tools)


def _derive_non_applicable(events: list[dict]) -> list[str]:
    """Derive non-applicability conditions from negative outcomes."""
    conditions = []
    for ev in events:
        payload = _event_payload(ev)
        et = ev.get("event_type", "")
        if et == "policy_checked" and payload.get("decision", "").lower() in ("deny", "ask"):
            # The workflow was blocked by policy — not applicable when same policy conditions
            conditions.append("policy_deny")
        if et == "step_executed" and payload.get("success") is False:
            error = payload.get("error", "")
            if "timeout" in str(error).lower():
                conditions.append("timeout_prone_context")
    return list(dict.fromkeys(conditions))  # dedupe, preserve order


def _derive_criteria(events: list[dict]) -> tuple[list[str], list[str]]:
    """Derive success/failure criteria from the trace."""
    success = []
    failure = []
    for ev in events:
        payload = _event_payload(ev)
        et = ev.get("event_type", "")
        if et == "execution_completed":
            if payload.get("success", True):
                success.append("execution_completed_success")
            else:
                failure.append("execution_failed")
        if et == "task_completed":
            outcome = payload.get("outcome", "")
            if outcome:
                success.append(f"task_outcome_{redact_payload(str(outcome))[:50]}")
        if et == "repetition_detected":
            failure.append("repetition_detected")
        if et == "task_stalled":
            failure.append("task_stalled")
    if not success:
        success.append("no_error_after_execution")
    return success, failure


# ---------------------------------------------------------------------------
# Duplicate detection (E3-11)
# ---------------------------------------------------------------------------

def compute_candidate_signature(draft: CandidateDraft) -> str:
    """Compute a canonical signature for duplicate detection (E3-11).

    Two drafts with the same signature are exact duplicates.
    Overlapping drafts have similar signatures (same trigger + category).
    """
    sig_fields = f"{draft.trigger}|{draft.category}|{draft.description.strip()}"
    return hashlib.sha256(sig_fields.encode()).hexdigest()


def compute_overlap_signature(draft: CandidateDraft) -> str:
    """Coarser signature for overlap detection (E3-11)."""
    return f"{draft.trigger}|{draft.category}"


async def detect_duplicate_candidates(
    fabric: SkillFabric,
    new_draft: CandidateDraft,
) -> list[SkillManifest]:
    """Detect exact duplicates and overlapping trigger candidates (E3-11).

    Returns list of existing skills that are duplicates or overlaps.
    """
    duplicates = []

    for manifest in fabric.list_all():
        # Exact duplicate: same source hash or draft content
        if manifest.source == "candidate":
            existing = fabric.get_manifest(manifest.name)
            if existing and existing.metadata.data.get("source_hash") == new_draft.source_hash:
                duplicates.append(manifest)
                continue

        # Overlap: same trigger + category
        if (manifest.trigger.strip().lower() == new_draft.trigger.strip().lower()
                and manifest.category == new_draft.category):
            duplicates.append(manifest)

    return duplicates


# ---------------------------------------------------------------------------
# Approval workflow (E3-12, E3-13, E3-18)
# ---------------------------------------------------------------------------

@dataclass
class CandidateDiff:
    """A diff presentation for approval (E3-12)."""
    name: str
    new_version: str
    changes: dict[str, tuple[Any, Any]]  # field -> (old, new)
    provenance: str
    expected_effect: str


async def prepare_candidate_diff(
    fabric: SkillFabric,
    draft: CandidateDraft,
) -> CandidateDiff:
    """Prepare a diff for approval presentation (E3-12)."""
    existing = fabric.get_manifest(draft.name)
    changes = {}

    fields_to_compare = [
        "trigger", "description", "body", "category", "allowed_tools",
        "non_applicable_when", "input_schema", "output_schema",
        "success_criteria", "failure_criteria", "expected_effect",
    ]

    for field in fields_to_compare:
        old_val = getattr(existing, field, None) if existing else None
        new_val = getattr(draft.to_manifest(), field, None)
        if old_val != new_val:
            changes[field] = (old_val, new_val)

    provenance = f"trace: {draft.trace_links[0].task_id}" if draft.trace_links else "unknown"
    return CandidateDiff(
        name=draft.name,
        new_version=draft.skill_version,
        changes=changes,
        provenance=provenance,
        expected_effect=draft.expected_effect,
    )


# ---------------------------------------------------------------------------
# Governance API (E3-25)
# ---------------------------------------------------------------------------

class SkillGovernance:
    """Governance interface for skill lifecycle (E3-25).

    Migrates governance into the existing SkillFabric: proves that
    `enabled=True` and the legacy registry table cannot bypass
    reviewed `ACTIVE` state.
    """

    def __init__(self, fabric: SkillFabric):
        self.fabric = fabric

    async def submit_and_register(self, draft: CandidateDraft) -> SkillManifest:
        """Submit a candidate draft and register it (E3-09, E3-25).

        The skill enters as CANDIDATE state. The `enabled` flag on the
        manifest is True, but state=CANDIDATE means it cannot execute.
        """
        manifest = draft.to_manifest()
        # Store provenance in metadata
        manifest.metadata.data["source_hash"] = draft.source_hash
        manifest.metadata.data["draft_hash"] = draft.draft_hash
        manifest.metadata.data["trace_links"] = [tl.__dict__ for tl in draft.trace_links]
        manifest.metadata.data["submitted_at"] = datetime.now(UTC).isoformat()

        await self.fabric.submit_candidate(manifest)
        return manifest

    async def promote_to_active(
        self, name: str, approver: str, notes: str = "",
    ) -> bool:
        """Promote a REVIEWED skill to ACTIVE with explicit approval (E3-18)."""
        manifest = self.fabric.get_manifest(name)
        if manifest is None or manifest.state != SkillState.REVIEWED:
            return False
        return await self.fabric.approve_skill(name, approver, notes)

    async def reject_and_suppress(self, name: str, rejector: str, reason: str) -> bool:
        """Reject a skill and suppress re-proposal of the same version (E3-13)."""
        manifest = self.fabric.get_manifest(name)
        if manifest is None:
            return False
        return await self.fabric.reject_skill(name, rejector, reason)

    def is_executable(self, name: str) -> bool:
        """Check if a skill is truly executable (ACTIVE state) (E3-25).

        This proves that `enabled=True` alone does NOT bypass the ACTIVE gate.
        """
        manifest = self.fabric.get_manifest(name)
        if manifest is None:
            return False
        if manifest.state != SkillState.ACTIVE:
            return False
        # Also check enabled flag — both must be True
        return manifest.enabled

    async def rollback(self, name: str, to_version: str | None = None) -> bool:
        """Rollback to a prior version (E3-19)."""
        return await self.fabric.rollback_skill(name, to_version)
