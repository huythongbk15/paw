"""Structured local-write demo using real review, operation approval and runtime.

Both review=True and approve=True are explicit fixture decisions. Raw approval
alone is not implementation authority. Content read-back is OBSERVED, not an
engineering verification record.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from paw.application.chat import ChatService
from paw.core.approval import ApprovalStore
from paw.core.storage import db, set_db_path


async def run_change_demo(approve=True, work_dir="/tmp/paw_beta_change", *, review=False) -> dict:
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    await set_db_path(work_dir / "demo.db")
    service = ChatService("local", workspace_root=work_dir)
    await service.open()
    reply = await service.send("tạo file changed_file.txt nội dung: PAW beta change demo.")
    review_id = reply.approval_id
    if review and review_id:
        reply = await service.approve()
    if approve and review and reply.status == "waiting_approval":
        reply = await service.approve()
    elif not approve and reply.approval_id:
        await ApprovalStore.deny(reply.approval_id, "demo-user")
        reply = await service.resume()
    changed = reply.status == "completed" and reply.executor == "local-filesystem"
    observed = False
    if changed:
        read = await service.send("đọc file changed_file.txt")
        observed = read.status == "completed" and "PAW beta change demo." in read.content
    result = {
        "stopped": True, "task_id": reply.task_id, "status": reply.status,
        "evidence": [{"type": "change_record", "decision_review_id": review_id,
                      "review_requested": review, "approved": approve,
                      "file_written": changed, "content_observed": observed}],
        "uncertainty": {"confidence": 1.0, "approval_granted": approve,
                        "file_written": changed, "content_observed": observed,
                        "verification_passed": False},
        "next_action": ("Content OBSERVED; declare engineering verification before VERIFIED."
                        if changed else
                        "Change denied; no write occurred." if not approve else
                        "Review decision, then approve the exact operation; no write occurred."),
    }
    await service.close()
    await db.close()
    return result


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run_change_demo(approve=False)), indent=2, ensure_ascii=False))
