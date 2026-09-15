"""PAW TUI — Textual 3-panel interactive agent UI.

Layout: conversation (left, 3/4) | sidebar (right, 1/4) | input (bottom).

Token-by-token streaming of model output via ChatService.send_streaming().

Design inspired by OpenCode's clean terminal aesthetic:
- Each message is a separate widget in a scrollable container (no full re-render)
- User messages: blue left border, right-aligned header
- Assistant messages: green left border, left-aligned header
- Status messages: muted dim style with colored icon
- Thinking: collapsible details block
- Compact sidebar with session info + inspection command list
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import (
    Footer,
    Header,
    Input,
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
    ("plan", "📋 Kế hoạp"),
    ("why", "🤔 Tại sao"),
    ("ledger", "📒 Nhật ký"),
    ("checkpoint", "💾 Checkpoint"),
    ("policy", "🛡️ Chính sách"),
    ("skills", "🔧 Kỹ năng"),
    ("artifacts", "📦 Artifacts"),
]


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


class UserMessage(Static):
    """A user message widget with blue accent."""

    DEFAULT_CSS = """
    UserMessage {
        border-left: solid cyan;
        padding: 0 0 0 2;
        margin: 0 0 1 0;
    }
    """

    def __init__(self, content: str, **kwargs: Any) -> None:
        super().__init__(content, **kwargs)


class AssistantMessage(Static):
    """An assistant message widget with green accent."""

    DEFAULT_CSS = """
    AssistantMessage {
        border-left: solid green;
        padding: 0 0 0 2;
        margin: 0 0 1 0;
    }
    """

    def __init__(self, content: str, **kwargs: Any) -> None:
        super().__init__(content, **kwargs)


class StatusMessage(Static):
    """A status message widget (dim, muted)."""

    DEFAULT_CSS = """
    StatusMessage {
        color: $text-muted;
        text-style: dim;
        padding: 0 0 0 1;
        margin: 0 0 0 0;
    }
    """

    def __init__(self, content: str, **kwargs: Any) -> None:
        super().__init__(content, **kwargs)


class PawTuiApp(App):
    """PAW TUI — 3-panel agent chat with token streaming."""

    CSS = """
    /* ── Global ────────────────────────── */
    Screen {
        layout: vertical;
        background: $surface;
        color: $foreground;
    }

    Header {
        background: $panel;
        color: $primary;
        text-style: bold;
    }

    Footer {
        background: $panel;
        color: $text-muted;
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

    #messages {
        height: 1fr;
        width: 100%;
        padding: 0 1;
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
        padding: 1;
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
        self._current_worker: Any | None = None
        self._current_assistant_widget: AssistantMessage | None = None
        self._stream_buffer: str = ""
        self._thinking: str = ""
        self._sidebar_visible: bool = True

    # ── Composition ─────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header("✧ PAW TUI")
        with Vertical(id="main-area"):
            with VerticalScroll(
                Vertical(id="messages"),
                id="conversation",
            ):
                pass
            yield Sidebar(id="sidebar")
        with Vertical(id="input-wrapper"):
            yield Input(
                placeholder="Nhắn tin... (gõ /help để xem lệnh)",
                id="message-input",
                select_on_focus=False,
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

    # ── Message rendering ───────────────────────────────────────────

    def _get_messages(self) -> Vertical:
        return self.query_one("#messages", Vertical)

    async def _scroll_to_bottom(self) -> None:
        conv = self.query_one("#conversation", VerticalScroll)
        # scroll_to is synchronous in Textual 8.x; just call it
        conv.scroll_to(y=1000000, animate=False)

    def _thinking_block(self) -> str:
        """Render thinking as a collapsible details block, or empty string."""
        if not self._thinking:
            return ""
        return (
            f"<details><summary>🧠 Suy nghĩ</summary>\n\n"
            f"{self._thinking}\n\n</details>\n\n"
        )

    def _format_assistant_msg(self) -> str:
        """Format the full assistant message (header + thinking + content)."""
        ts = _timestamp()
        return (
            f"**🤖 Trợ lý PAW** _• {ts}_\n\n"
            f"{self._thinking_block()}"
            f"{self._stream_buffer}"
        )

    async def _add_user_message(self, content: str) -> None:
        ts = _timestamp()
        widget = UserMessage(
            f"**👤 Bạn** _• {ts}_\n\n{content}",
        )
        await self._get_messages().mount(widget)
        await self._scroll_to_bottom()

    async def _start_streaming(self) -> None:
        self._stream_buffer = ""
        self._thinking = ""
        ts = _timestamp()
        widget = AssistantMessage(
            f"**🤖 Trợ lý PAW** _• {ts}_\n\n",
        )
        await self._get_messages().mount(widget)
        self._current_assistant_widget = widget
        await self._scroll_to_bottom()

    async def _append_token(self, token: str) -> None:
        """Append a token to the streaming message and update the widget."""
        self._stream_buffer += token
        if self._current_assistant_widget is not None:
            self._current_assistant_widget.update(self._format_assistant_msg())
            await self._scroll_to_bottom()

    async def _finish_streaming(self) -> None:
        """Finalize the streaming message (update timestamp one last time)."""
        if self._current_assistant_widget is not None:
            self._current_assistant_widget.update(self._format_assistant_msg())
            self._current_assistant_widget = None
            await self._scroll_to_bottom()

    async def _add_status(self, content: str, level: str = "info") -> None:
        icon = {"info": "•", "warning": "⚠", "error": "✗", "success": "✓"}.get(level, "•")
        ts = _timestamp()
        widget = StatusMessage(f"[{icon} {ts}] {content}")
        await self._get_messages().mount(widget)
        await self._scroll_to_bottom()

    # ── Message handling ────────────────────────────────────────────

    def _clear_input(self) -> None:
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
            self._stream_buffer += f"\n[Lỗi: {exc}]"
            await self._append_token("")
            sidebar.set_status("Lỗi")
        finally:
            self._streaming = False
            self.query_one("#message-input", Input).disabled = False
            self.query_one("#message-input", Input).focus()
            await self._finish_streaming()
            sidebar.set_status("Sẵn sàng")

    async def _handle_stream_event(
        self, event: StreamEvent, sidebar: Sidebar
    ) -> None:
        """Process a single StreamEvent from the streaming pipeline."""
        if event.event_type == "thinking":
            self._thinking += event.content or ""
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
            self._stream_buffer += f"\n[Lỗi: {event.content}]"
            await self._append_token("")
            sidebar.set_status("Lỗi")

    # ── Command handling ────────────────────────────────────────────

    async def _handle_command(self, cmd: str) -> None:
        parts = cmd[1:].split(None, 1)
        command = parts[0] if parts else ""

        if command == "help":
            help_text = (
                "**📋 Lệnh TUI**\n\n"
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
            )
            await self._add_status(help_text, "info")
        elif command == "clear":
            messages = self._get_messages()
            for child in list(messages.children):
                child.remove()
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

        key = option.id
        if key and key in dict(_INSPECT_COMMANDS):
            inp = self.query_one("#message-input", Input)
            inp.value = f"/{key}"
            inp.action_submit()

    # ── Action handlers ──────────────────────────────────────────────

    def action_refresh_sidebar(self) -> None:
        self.query_one(Sidebar).set_status("Làm mới…")

    def action_clear(self) -> None:
        messages = self._get_messages()
        for child in list(messages.children):
            child.remove()

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
        if self._current_worker is not None and getattr(
            self._current_worker, "is_running", False
        ):
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
