"""Workspace-scoped local filesystem executor."""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from typing import ClassVar

from paw.core.executor import EffectIntent, ExecutableTask, Executor, ExecutorResult
from paw.core.models import Capability
from paw.core.task import Task


class LocalFilesystemExecutor(Executor):
    """Perform explicit read/list/write operations inside one workspace.

    The runtime is responsible for Policy and approval before this adapter is
    invoked. The adapter independently enforces its filesystem boundary so a
    malformed or approved traversal path still cannot escape the workspace.
    """

    name = "local-filesystem"
    capabilities: ClassVar[list[Capability]] = [
        Capability.FILESYSTEM_READ,
        Capability.FILESYSTEM_WRITE,
    ]
    max_read_bytes = 1_000_000
    max_list_entries = 500

    def __init__(self, workspace_root: str | Path):
        root = Path(workspace_root).resolve()
        if not root.is_dir():
            raise ValueError(f"workspace root is not a directory: {root}")
        self.workspace_root = root

    def _target(self, raw_path: str) -> tuple[Path, str]:
        if not raw_path or "\x00" in raw_path:
            raise ValueError("filesystem path is empty or invalid")
        requested = Path(raw_path)
        unresolved = requested if requested.is_absolute() else self.workspace_root / requested
        # Keep the lexical path so writes can reject symlink components; using
        # Path.resolve() here would erase precisely the link we must detect.
        candidate = Path(os.path.abspath(unresolved))  # noqa: PTH100
        resolved = candidate.resolve(strict=False)
        if not candidate.is_relative_to(self.workspace_root) or not resolved.is_relative_to(
            self.workspace_root
        ):
            raise ValueError(f"path is outside workspace: {raw_path}")
        relative = candidate.relative_to(self.workspace_root).as_posix()
        return candidate, relative or "."

    def _write_uses_symlink(self, target: Path) -> bool:
        current = self.workspace_root
        for part in target.relative_to(self.workspace_root).parts:
            current /= part
            if current.is_symlink():
                return True
        return False

    async def execute(
        self,
        task: Task | ExecutableTask,
        context: str,
    ) -> ExecutorResult:
        del context
        metadata = getattr(task, "metadata", {}) or {}
        request = metadata.get("filesystem")
        if not isinstance(request, dict):
            return ExecutorResult(
                success=False,
                error="missing structured filesystem operation",
            )

        operation = str(request.get("operation") or "").lower()
        try:
            target, relative = self._target(str(request.get("path") or "."))
            if operation == "read":
                return self._read(target, relative)
            if operation == "list":
                return self._list(target, relative)
            if operation == "write":
                return self._write(
                    target,
                    relative,
                    str(request.get("content") or ""),
                    str(request.get("mode") or "create"),
                )
            return ExecutorResult(
                success=False,
                error=f"unsupported filesystem operation: {operation or '<empty>'}",
            )
        except (OSError, UnicodeError, ValueError) as exc:
            return ExecutorResult(success=False, error=str(exc))

    async def prepare_effect(
        self,
        task: Task | ExecutableTask,
        context: str,
    ) -> EffectIntent | None:
        """Capture a write intent before the filesystem can be changed."""
        del context
        prepared = self._write_request(task)
        if prepared is None:
            return None
        target, request = prepared
        mode = request["mode"]
        if target.exists() and target.is_dir():
            return None
        if self._write_uses_symlink(target):
            return None
        if mode == "create" and target.exists():
            return None

        precondition: dict[str, object] = {"exists": target.is_file()}
        if target.is_file():
            precondition["content_sha256"] = self._file_sha256(target)
        return EffectIntent(
            executor=self.name,
            operation_id=str(getattr(task, "operation_id", "")),
            idempotency_key=str(
                getattr(task, "idempotency_key", None)
                or getattr(task, "operation_id", "")
            ),
            request=request,
            precondition=precondition,
        )

    async def reconcile_effect(
        self,
        task: Task | ExecutableTask,
        context: str,
        intent: EffectIntent,
    ) -> ExecutorResult:
        """Prove an interrupted write by comparing its durable final state."""
        del context
        prepared = self._write_request(task)
        if prepared is None:
            return self._ambiguous("current proposal is not the prepared filesystem write")
        target, request = prepared
        expected_key = str(
            getattr(task, "idempotency_key", None)
            or getattr(task, "operation_id", "")
        )
        if (
            intent.executor != self.name
            or intent.operation_id != str(getattr(task, "operation_id", ""))
            or intent.idempotency_key != expected_key
            or intent.request != request
        ):
            return self._ambiguous("current proposal does not match the prepared effect")
        if self._write_uses_symlink(target):
            return self._ambiguous("prepared target now traverses a symbolic link")
        if not target.is_file():
            return self._ambiguous("prepared target is absent or is not a file")
        try:
            current_hash = self._file_sha256(target)
        except OSError as exc:
            return self._ambiguous(f"prepared target cannot be read: {exc}")
        if current_hash != request["content_sha256"]:
            return self._ambiguous("prepared target content differs from the intended effect")

        relative = str(request["path"])
        encoded_size = int(request["bytes"])
        artifact_operation = "created" if request["mode"] == "create" else "replaced"
        artifact = {
            "type": "file",
            "path": relative,
            "operation": artifact_operation,
            "bytes": encoded_size,
        }
        return ExecutorResult(
            success=True,
            output=f"Đã xác nhận `{relative}` ({encoded_size} bytes) sau khi resume.",
            artifacts=[artifact],
            metadata={
                "filesystem": artifact,
                "reconciliation": "applied",
            },
        )

    def _write_request(
        self,
        task: Task | ExecutableTask,
    ) -> tuple[Path, dict[str, object]] | None:
        metadata = getattr(task, "metadata", {}) or {}
        raw_request = metadata.get("filesystem")
        if not isinstance(raw_request, dict):
            return None
        if str(raw_request.get("operation") or "").lower() != "write":
            return None
        mode = str(raw_request.get("mode") or "create")
        if mode not in {"create", "replace"}:
            return None
        try:
            target, relative = self._target(str(raw_request.get("path") or "."))
        except ValueError:
            return None
        content = str(raw_request.get("content") or "")
        encoded = content.encode("utf-8")
        return target, {
            "operation": "write",
            "path": relative,
            "mode": mode,
            "content_sha256": hashlib.sha256(encoded).hexdigest(),
            "bytes": len(encoded),
        }

    @staticmethod
    def _file_sha256(target: Path) -> str:
        digest = hashlib.sha256()
        with target.open("rb") as handle:
            for block in iter(lambda: handle.read(64 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _ambiguous(reason: str) -> ExecutorResult:
        return ExecutorResult(
            success=False,
            error=f"prepared filesystem effect is ambiguous: {reason}",
            metadata={"reconciliation": "ambiguous"},
        )

    def _read(self, target: Path, relative: str) -> ExecutorResult:
        if not target.is_file():
            return ExecutorResult(success=False, error=f"file not found: {relative}")
        size = target.stat().st_size
        if size > self.max_read_bytes:
            return ExecutorResult(
                success=False,
                error=f"file exceeds read limit ({size} > {self.max_read_bytes} bytes)",
            )
        content = target.read_text(encoding="utf-8", errors="replace")
        return ExecutorResult(
            success=True,
            output=content,
            metadata={"operation": "read", "path": relative, "bytes": size},
        )

    def _list(self, target: Path, relative: str) -> ExecutorResult:
        if not target.is_dir():
            return ExecutorResult(success=False, error=f"directory not found: {relative}")
        entries = sorted(target.iterdir(), key=lambda path: path.name.casefold())
        truncated = len(entries) > self.max_list_entries
        entries = entries[: self.max_list_entries]
        rendered = [f"{entry.name}/" if entry.is_dir() else entry.name for entry in entries]
        return ExecutorResult(
            success=True,
            output="\n".join(rendered),
            metadata={
                "operation": "list",
                "path": relative,
                "entries": len(rendered),
                "truncated": truncated,
            },
        )

    def _write(
        self,
        target: Path,
        relative: str,
        content: str,
        mode: str,
    ) -> ExecutorResult:
        if mode not in {"create", "replace"}:
            return ExecutorResult(success=False, error=f"unsupported write mode: {mode}")
        if target.exists() and target.is_dir():
            return ExecutorResult(success=False, error=f"target is a directory: {relative}")
        if self._write_uses_symlink(target):
            return ExecutorResult(success=False, error=f"symbolic-link writes are denied: {relative}")
        if mode == "create" and target.exists():
            return ExecutorResult(success=False, error=f"file already exists: {relative}")

        target.parent.mkdir(parents=True, exist_ok=True)
        encoded_size = len(content.encode("utf-8"))
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=target.parent,
                prefix=f".{target.name}.",
                suffix=".paw-tmp",
                delete=False,
            ) as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
                temporary_path = Path(handle.name)

            if mode == "create":
                os.link(temporary_path, target)
                temporary_path.unlink()
                temporary_path = None
                artifact_operation = "created"
            else:
                temporary_path.replace(target)
                temporary_path = None
                artifact_operation = "replaced"
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()

        artifact = {
            "type": "file",
            "path": relative,
            "operation": artifact_operation,
            "bytes": encoded_size,
        }
        return ExecutorResult(
            success=True,
            output=f"Đã {artifact_operation} `{relative}` ({encoded_size} bytes).",
            artifacts=[artifact],
            metadata={"filesystem": artifact},
        )
