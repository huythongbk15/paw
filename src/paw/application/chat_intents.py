"""Deterministic chat intent projection for the local product slice."""

from __future__ import annotations

import re
from typing import Any

from paw.core.models import Capability


def parse_filesystem_intent(message: str) -> dict[str, Any] | None:
    """Parse the deliberately narrow read/list/write chat grammar."""
    normalized = message.strip()
    write_match = re.match(
        r"^(?:hãy\s+)?(?P<verb>tạo|create|ghi|write|sửa|edit)\s+"
        r"(?:file|tệp)?\s*[`'\"]?(?P<path>[^\s`'\"]+)[`'\"]?\s+"
        r"(?:với\s+)?(?:nội\s+dung|content)\s*:\s*(?P<content>.*)$",
        normalized,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if write_match:
        verb = write_match.group("verb").lower()
        return {
            "operation": "write",
            "path": write_match.group("path"),
            "content": write_match.group("content"),
            "mode": "create" if verb in {"tạo", "create"} else "replace",
        }

    read_match = re.match(
        r"^(?:hãy\s+)?(?:đọc|read|xem)\s+(?:file|tệp)?\s*"
        r"[`'\"]?(?P<path>[^\s`'\"]+)[`'\"]?\s*$",
        normalized,
        flags=re.IGNORECASE,
    )
    if read_match:
        return {"operation": "read", "path": read_match.group("path")}

    list_match = re.match(
        r"^(?:hãy\s+)?(?:liệt\s+kê|list)\s+(?:thư\s+mục|directory)?\s*"
        r"[`'\"]?(?P<path>[^\s`'\"]*)[`'\"]?\s*$",
        normalized,
        flags=re.IGNORECASE,
    )
    if list_match:
        return {"operation": "list", "path": list_match.group("path") or "."}
    return None


def change_preview(intent: dict[str, Any]) -> str | None:
    """Render proposed full content without reading the target before Policy."""
    if intent.get("operation") != "write":
        return None
    path = str(intent["path"])
    mode = str(intent.get("mode") or "create")
    content = str(intent.get("content") or "")
    additions = "\n".join(f"+{line}" for line in content.splitlines())
    if content.endswith("\n"):
        additions += "\n+"
    return f"--- {path}\n+++ {path}\n@@ proposed {mode} content @@\n{additions}"


def infer_capabilities(message: str) -> list[Capability]:
    """Conservatively project natural-language intent to action capabilities."""
    normalized = re.sub(r"\s+", " ", message.strip().lower())
    filesystem_intent = parse_filesystem_intent(message)
    if filesystem_intent:
        if filesystem_intent["operation"] == "write":
            return [Capability.FILESYSTEM_WRITE]
        return [Capability.FILESYSTEM_READ]

    capabilities: list[Capability] = []
    rules: list[tuple[Capability, tuple[str, ...]]] = [
        (Capability.FILESYSTEM_DELETE, ("delete file", "remove file", "xóa file", "xoá file")),
        (Capability.GIT_WRITE, ("git commit", "git push", "commit code", "push code")),
        (Capability.SHELL_EXECUTE, ("run command", "execute command", "chạy lệnh", "thực thi lệnh")),
        (Capability.FILESYSTEM_WRITE, ("write file", "create file", "edit file", "ghi file", "tạo file", "sửa file")),
        (Capability.NETWORK_HTTP, ("http://", "https://", "browse web", "search web", "tra cứu web")),
        (Capability.FILESYSTEM_READ, ("read file", "đọc file", "inspect file", "xem file")),
        (Capability.GIT_READ, ("git status", "git log", "xem git")),
    ]
    for capability, markers in rules:
        if any(marker in normalized for marker in markers):
            capabilities.append(capability)
    capabilities.insert(0, Capability.MODEL_INFERENCE)
    return list(dict.fromkeys(capabilities))


__all__ = ["change_preview", "infer_capabilities", "parse_filesystem_intent"]
