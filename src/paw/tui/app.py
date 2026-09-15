"""PAW TUI — Textual 3-panel interactive agent UI.

Layout: conversation (left, 3/4) | sidebar (right, 1/4) | input (bottom).

Token-by-token streaming of model output via ChatService.send_streaming().

Inspired by OpenCode's clean terminal aesthetic: minimal borders,
distinct color-coded message blocks, compact sidebar, and inline
thinking.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import (
    Footer,
    Header,
    Input,
    Markdown,
    OptionList,
    Static,
)
from textual.widgets._option_list import Option

from paw.application.chat import ChatService, StreamEvent
from paw.core.logging import get_logger
from paw.core.storage import db

log = get_logger(__name__)

# Sidebar inspection commands in display order.
_INSPECT_COMMANDS = [
    ("status", "📊 Trạng thái"),
    ("plan", "📋 Kế hoạch"),
    ("why", "🤔 Tại sao"),
    ("ledger", "📒 Nhật ký"),
    ("checkpoint", "💾 Checkpoint"),
    ("policy", "🛡️ Chính sách"),
    ("skills", "🔧 Kỹ năng"),
    ("artifacts", "📦 Artifacts"),
]

# ANSI-ish color tokens for message prefixes (rendered in markdown via HTML spans).
_USER_COLOR = "#4da6ff"
_ASSISTANT_COLOR = "#66cc66"
_STATUS_COLORS = {
    "info": "#66cc66",
    "warning": "#ffaa00",
    "error": "#ff6666",
    "success": "#66cc66",
}


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%H:%M:%S")


class Sidebar(Vertical):
    """Right sidebar: session info + inspection command list."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._session_id: str = ""
        self._provider: str = ""
        self._message_count: int = 0
        self._status_text: str = "Chưa kết nối"

    def compose(self) -> ComposeResult:
        yield OptionList(id="inspect-list")
        yield Static("", id="session-info")

    def on_mount(self) -> None:
        ol = self.query_one(OptionList)
        for key, label in _INSPECT_COMMANDS:
            ol.add_option(Option(label, id=key))
        self._render_session_info()

    def set_session(self, session_id: str, provider: str) -> None:
        self._session_id = session_id
        self._provider = provider
        self._message_count = 0
        self._render_session_info()

    def set_status(self, status: str) -> None:
        self._status_text = status
        self._render_session_info()

    def increment_messages(self) -> None:
        self._message_count += 1
        self._render_session_info()

    def _render_session_info(self) -> None:
        sid = self._session_id[:8] or "——"
        content = (
            f"  #{sid}\n"
            f"  {self._provider}\n"
            f"  {self._message_count} messages\n"
            f"  {self._status_text}"
        )
        self.query_one("#session-info", Static).update(content)


class PawTuiApp(App):
    """PAW TUI — 3-panel agent chat with token streaming."""

    CSS = """
    /* ── Global ────────────────────────── */
    Screen {
        layout: vertical;
        background: $surface;
        color: $foreground;
    }

    /* ── Main area ────────────────────── */
    #main-area {
        height: 1fr;
        layout: horizontal;
    }

    /* ── Conversation pane ────────────── */
    #conversation {
        width: 3fr;
        height: 1fr;
        border-right: solid $primary;
        background: $panel;
    }

    /* ── Sidebar ──────────────────────── */
    #sidebar {
        width: 26;
        border-left: solid $primary;
        background: $boost;
        layout: vertical;
    }

    #inspect-list {
        height: 1fr;
        border: none;
        padding: 1 1;
    }

    #inspect-list OptionList.item-highlighted {
        color: $text;
        background: $primary 30%;
    }

    #session-info {
        height: auto;
        border-top: solid $primary;
        padding: 0 1;
        color: $text-muted;
        text-style: dim;
        layers: base;
    }

    #session-info.-focused {
        color: $text;
        text-style: bold;
    }

    /* ── Input area ───────────────────── */
    #input-wrapper {
        height: 3;
        border: solid $accent;
        padding: 0 1;
        background: $panel;
    }

    #message-input {
        width: 100%;
        height: 1;
        border: none;
        padding: 0;
        color: $text;
        background: transparent;
    }

    /* ── Status message styling ───────── */
    Markdown .paw-status {
        padding: 0 0 0 2;
        color: $text-muted;
        text-style: dim;
    }
    """

    BINDINGS: ClassVar = [
        ("ctrl+c", "quit", "Thoát"),
        ("ctrl+r", "refresh_sidebar", "Làm mới"),
        ("ctrl+l", "clear", "Xóa màn hình"),
        ("ctrl+s", "toggle_sidebar", "Bật/tắt sidebar"),
    ]

    def __init__(
        self,
        *args: Any,
        provider_mode: str = "auto",
        workspace: str | Path = ".",
        session_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.provider_mode = provider_mode
        self.workspace = Path(workspace).resolve()
        self.requested_session_id = session_id
        self._service: ChatService | None = None
        self._session_id: str = ""
        self._streaming: bool = False
        self._current_worker: asyncio.Task[None] | None = None
        self._history_parts: list[str] = []
        self._current_stream_buf: str = ""
        self._thinking_buf: str = ""
        self._sidebar_visible: bool = True

    # ── Composition ─────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header("✧ PAW TUI")
        with Vertical(id="main-area"):
            yield Markdown("", id="conversation")
            yield Sidebar(id="sidebar")
        with Vertical(id="input-wrapper"):
            yield Input(
                placeholder="Nhắn tin... (gõ /help để xem lệnh)",
                id="message-input",
            )
        yield Footer()

    async def on_mount(self) -> None:
        """Initialize the chat service and session on startup."""
        self._service = ChatService(
            provider_mode=self.provider_mode,
            workspace_root=str(self.workspace),
        )
        try:
            session = await self._service.open(self.requested_session_id)
            self._session_id = session.session_id
            sidebar = self.query_one(Sidebar)
            sidebar.set_session(session.session_id, self.provider_mode)
            sidebar.set_status("Sẵn sàng")
            await self._add_status(
                f"Kết nối với PAW • session {self._session_id[:8]}…",
                "success",
            )
        except Exception as exc:
            log.error("tui_init_failed", error=str(exc))
            await self._add_status(f"Lỗi khởi tạo: {exc}", "error")
            self.query_one(Sidebar).set_status("Lỗi")

        self.query_one("#message-input", Input).focus()

    # ── Conversation rendering ───────────────────────────────────────

    async def _render_conversation(self) -> None:
        """Rebuild and render the full conversation markdown."""
        md = self.query_one("#conversation", Markdown)
        await md.update("\n\n".join(self._history_parts) or "")
        md.scroll_to(y=1000000, animate=False)

    async def _add_user_message(self, content: str) -> None:
        ts = _timestamp()
        self._history_parts.append(
            f'<div class="paw-user" style="border-left: 2px solid {_USER_COLOR}; padding-left: 8px;">'
            f'<strong>👤 Bạn</strong> <span style="color: {_USER_COLOR};">• {ts}</span>\n\n'
            f"{content}</div>"
        )
        await self._render_conversation()

    async def _start_streaming(self) -> None:
        self._current_stream_buf = ""
        self._thinking_buf = ""
        ts = _timestamp()
        self._history_parts.append(
            f'<div class="paw-assistant" style="border-left: 2px solid {_ASSISTANT_COLOR}; padding-left: 8px;">'
            f'<strong>🤖 Trợ lý PAW</strong> '
            f'<span style="color: {_ASSISTANT_COLOR};">• {ts}</span>\n\n'
            f"{self._current_stream_buf}</div>"
        )
        await self._render_conversation()

    async def _append_token(self, token: str) -> None:
        self._current_stream_buf += token
        # Rebuild the last message block with updated content
        ts = _timestamp()
        self._history_parts[-1] = (
            f'<div class="paw-assistant" style="border-left: 2px solid {_ASSISTANT_COLOR}; padding-left: 8px;">'
            f'<strong>🤖 Trợ lý PAW</strong> '
            f'<span style="color: {_ASSISTANT_COLOR};">• {ts}</span>\n\n'
            f"{self._current_stream_buf}</div>"
        )
        await self._render_conversation()

    async def _finish_streaming(self, thinking: str | None = None) -> None:
        ts = _timestamp()
        header = (
            f'<div class="paw-assistant" style="border-left: 2px solid {_ASSISTANT_COLOR}; padding-left: 8px;">'
            f'<strong>🤖 Trợ lý PAW</strong> '
            f'<span style="color: {_ASSISTANT_COLOR};">• {ts}</span>\n\n'
        )
        thinking_html = ""
        if thinking:
            thinking_html = (
                f'<details style="margin: 8px 0; padding: 4px 0; border-left: 1px solid {_ASSISTANT_COLOR};">'
                f'<summary style="color: {_ASSISTANT_COLOR}; cursor: pointer;">🧠 Suy nghĩ</summary>\n\n'
                f"{thinking}\n\n</details>\n\n"
            )
        self._history_parts[-1] = (
            header
            + thinking_html
            + f"{self._current_stream_buf}</div>"
        )
        await self._render_conversation()

    async def _add_status(self, content: str, level: str = "info") -> None:
        color = _STATUS_COLORS.get(level, _STATUS_COLORS["info"])
        icon = {"info": "•", "warning": "⚠", "error": "✗", "success": "✓"}.get(level, "•")
        ts = _timestamp()
        self._history_parts.append(
            f'<div class="paw-status" style="color: {color};">'
            f'[{icon} {ts}] {content}</div>'
        )
        await self._render_conversation()

    def _clear_conversation(self) -> None:
        self._history_parts = []
        self._current_stream_buf = ""
        self._thinking_buf = ""

    # ── Message handling ────────────────────────────────────────────

    def _clear_input(self) -> None:
        """Clear the input field value."""
        inp = self.query_one("#message-input", Input)
        inp.value = ""

    async def _on_message_submitted(self, value: str) -> None:
        """Handle user submitting a message from the input field."""
        if not value.strip():
            return

        stripped = value.strip()

        if stripped.startswith("/"):
            await self._handle_command(stripped)
            self._clear_input()
            return

        if self._streaming:
            await self._add_status("Đang xử lý... vui lòng chờ.", "warning")
            return

        self._streaming = True
        self.query_one("#message-input", Input).disabled = True
        await self._add_user_message(stripped)
        self._clear_input()
        self.query_one(Sidebar).increment_messages()
        self.query_one(Sidebar).set_status("Đang suy nghĩ...")

        self._current_worker = self.run_worker(
            self._stream_send(stripped),
            exclusive=True,
        )

    def _get_service(self) -> ChatService | None:
        return self._service

    async def _stream_send(self, message: str) -> None:
        """Consume streaming events and update the UI token-by-token."""
        service = self._get_service()
        if service is None:
            return
        sidebar = self.query_one(Sidebar)
        await self._start_streaming()
        sidebar.set_status("Đang phản hồi...")

        try:
            async for event in service.send_streaming(message):
                await self._handle_stream_event(event, sidebar)
        except Exception as exc:
            log.error("tui_stream_error", error=str(exc))
            await self._append_token(f"\n[Lỗi: {exc}]")
            sidebar.set_status("Lỗi")
        finally:
            self._streaming = False
            self.query_one("#message-input", Input).disabled = False
            self.query_one("#message-input", Input).focus()
            await self._finish_streaming(self._thinking_buf if self._thinking_buf else None)
            sidebar.set_status("Sẵn sàng")

    async def _handle_stream_event(
        self, event: StreamEvent, sidebar: Sidebar
    ) -> None:
        """Process a single StreamEvent from the streaming pipeline."""
        if event.event_type == "thinking":
            self._thinking_buf += event.content or ""
        elif event.event_type == "model_selected":
            model = event.data.get("model", "unknown")
            sidebar.set_status(f"Model: {model}")
        elif event.event_type == "token":
            await self._append_token(event.content or "")
        elif event.event_type == "complete":
            if event.reply:
                sidebar.set_status(
                    f"Hoàn thành • {event.reply.model or '—'}"
                )
                sidebar.increment_messages()
        elif event.event_type == "error":
            await self._add_status(f"Lỗi: {event.content}", "error")
            sidebar.set_status("Lỗi")

    # ── Command handling ────────────────────────────────────────────

    async def _handle_command(self, cmd: str) -> None:
        parts = cmd[1:].split(None, 1)
        command = parts[0] if parts else ""

        if command == "help":
            help_text = (
                '<div style="padding: 4px 0;">'
                "<strong>📋 Lệnh TUI</strong>\n"
                "| Lệnh | Mô tả |\n"
                "|------|-------|\n"
                "| `/status` | Trạng thái phiên |\n"
                "| `/plan` | Kế hoạch hiện tại |\n"
                "| `/why` | Giải thích quyết định |\n"
                "| `/ledger` | Nhật ký sự kiện |\n"
                "| `/checkpoint` | Thông tin checkpoint |\n"
                "| `/policy` | Trạng thái chính sách |\n"
                "| `/skills` | Kỹ năng/context |\n"
                "| `/artifacts` | Artifacts |\n"
                "| `/clear` | Xóa màn hình |\n"
                "| `/exit` | Thoát |\n"
                "</div>"
            )
            await self._add_status(help_text, "info")
        elif command == "clear":
            self._clear_conversation()
            await self._render_conversation()
            await self._add_status("Đã xóa cuộc trò chuyện.", "info")
        elif command in ("exit", "quit"):
            self.exit()
        else:
            await self._run_inspection(command)

    async def _run_inspection(self, kind: str) -> None:
        """Run an inspection command and display the result."""
        service = self._get_service()
        if service is None:
            await self._add_status("ChatService chưa sẵn sàng.", "error")
            return

        method_map = {
            "status": service.status,
            "plan": service.plan,
            "why": service.explain,
            "ledger": lambda: service.ledger(20),
            "checkpoint": service.checkpoint,
            "policy": service.policy,
            "skills": service.skills,
            "artifacts": lambda: service.artifacts(),
        }
        if kind not in method_map:
            await self._add_status(
                f"Lệnh không xác định: /{kind}. Gõ /help để xem lệnh.",
                "warning",
            )
            return

        try:
            result = await method_map[kind]()
            data_str = json.dumps(result or {}, indent=2, default=str)
            await self._add_status(
                f"**/{kind}**\n```json\n{data_str}\n```", "info"
            )
        except Exception as exc:
            await self._add_status(f"Lỗi khi chạy /{kind}: {exc}", "error")

    # ── Sidebar ─────────────────────────────────────────────────────

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        """Handle sidebar option selection."""
        option = event.option
        if option is None:
            return

        # The Option was added with (label, id=key) so option.id is the key
        key = option.id
        if key and key in dict(_INSPECT_COMMANDS):
            inp = self.query_one("#message-input", Input)
            inp.value = f"/{key}"
            inp.action_submit()

    # ── Action handlers ──────────────────────────────────────────────

    def action_refresh_sidebar(self) -> None:
        self.query_one(Sidebar).set_status("Làm mới…")

    def action_clear(self) -> None:
        self._clear_conversation()
        self.query_one("#conversation", Markdown).update("")

    def action_toggle_sidebar(self) -> None:
        sidebar = self.query_one("#sidebar")
        if self._sidebar_visible:
            sidebar.display = False
            self._sidebar_visible = False
        else:
            sidebar.display = True
            self._sidebar_visible = True

    # ── Cleanup ────────────────────────────────────────────────────

    async def on_unmount(self) -> None:
        """Clean up on exit."""
        if self._service:
            try:
                await self._service.close()
                await db.close()
            except Exception:
                pass
        if self._current_worker and not self._current_worker.done():
            self._current_worker.cancel()

    @on(Input.Submitted)
    async def on_message_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in the input field."""
        value = event.value
        await self._on_message_submitted(value)


def run_tui(
    provider_mode: str = "auto",
    workspace: str = ".",
    session_id: str | None = None,
) -> None:
    """Launch the PAW TUI."""
    app = PawTuiApp(
        provider_mode=provider_mode,
        workspace=workspace,
        session_id=session_id,
    )
    app.run()


__all__ = [
    "PawTuiApp",
    "run_tui",
]
