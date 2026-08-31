"""
PAW CLI — Command line interface for Personal Agent Workstation.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog
import typer
from rich.console import Console
from rich.table import Table

from .. import __version__
from ..core.config import settings
from ..core.storage import db

app = typer.Typer(
    name="paw",
    help="PAW — Personal Agent Workstation",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
)

console = Console()


def _print_chat_reply(reply: Any, json_output: bool) -> None:
    if json_output:
        typer.echo(json.dumps(reply.to_dict(), ensure_ascii=False))
        return
    console.print(f"[bold cyan]paw>[/bold cyan] {reply.content}")
    details = [f"status={reply.status}", f"session={reply.session_id}"]
    if reply.task_id:
        details.append(f"task={reply.task_id}")
    if reply.model:
        details.append(f"model={reply.model}")
    if reply.executor:
        details.append(f"executor={reply.executor}")
    console.print(f"[dim]{' | '.join(details)}[/dim]")


def _print_chat_status(status: dict[str, Any], json_output: bool = False) -> None:
    if json_output:
        typer.echo(json.dumps(status, ensure_ascii=False))
        return
    table = Table(show_header=False)
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    for key, value in status.items():
        table.add_row(key, "-" if value is None else str(value))
    console.print(table)


def _print_chat_history(messages: list[Any], json_output: bool = False) -> None:
    if json_output:
        typer.echo(
            json.dumps(
                [
                    {
                        "id": item.id,
                        "role": item.role.value,
                        "content": item.content,
                        "task_id": item.task_id,
                        "created_at": item.created_at.isoformat(),
                    }
                    for item in messages
                ],
                ensure_ascii=False,
            )
        )
        return
    if not messages:
        console.print("[dim]Chưa có tin nhắn.[/dim]")
        return
    for item in messages:
        color = "green" if item.role.value == "user" else "cyan"
        console.print(f"[{color}]{item.role.value}>[/{color}] {item.content}")


def version_callback(value: bool) -> None:
    if value:
        console.print(f"PAW version [bold]{__version__}[/bold]")
        raise typer.Exit()


@app.callback()
def main(
    _version: bool = typer.Option(
        False,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-V",
        help="Enable verbose output",
    ),
) -> None:
    """PAW — Personal Agent Workstation"""
    if verbose:
        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(structlog.DEBUG)
        )


@app.command()
def doctor() -> None:
    """Check PAW installation and configuration."""
    console.print("[bold]PAW Doctor[/bold]\n")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Details")

    # Check PAW home
    paw_home_exists = settings.paw_home.exists()
    table.add_row(
        "PAW Home",
        "[green]OK[/green]" if paw_home_exists else "[red]MISSING[/red]",
        str(settings.paw_home),
    )

    # Check database
    db_path = settings.db_path
    db_exists = db_path.exists()
    table.add_row(
        "Database",
        "[green]OK[/green]" if db_exists else "[yellow]NOT INITIALIZED[/yellow]",
        str(db_path),
    )

    # Check skills directory
    skills_path = settings.skills_path
    skills_exists = skills_path.exists()
    table.add_row(
        "Skills Dir",
        "[green]OK[/green]" if skills_exists else "[yellow]NOT CREATED[/yellow]",
        str(skills_path),
    )

    # Check knowledge directory
    knowledge_path = settings.knowledge_path
    knowledge_exists = knowledge_path.exists()
    table.add_row(
        "Knowledge Dir",
        "[green]OK[/green]" if knowledge_exists else "[yellow]NOT CREATED[/yellow]",
        str(knowledge_path),
    )

    console.print(table)

    if not db_exists:
        console.print("\n[yellow]Run 'paw init' to initialize the database.[/yellow]")
        raise typer.Exit(code=1)

    console.print("\n[green]All checks passed![/green]")


@app.command()
def init() -> None:
    """Initialize PAW database and directories."""
    console.print("[bold]Initializing PAW...[/bold]")

    # Create directories
    for path in [
        settings.paw_home,
        settings.skills_path,
        settings.knowledge_path,
        settings.artifacts_path,
        settings.cache_path,
        settings.logs_path,
    ]:
        path.mkdir(parents=True, exist_ok=True)
        console.print(f"  Created: {path}")

    # Initialize database
    asyncio.run(db.initialize())
    console.print(f"  Database initialized: {settings.db_path}")

    # Close database connection
    asyncio.run(db.close())

    console.print("\n[green]PAW initialized successfully![/green]")
    console.print("Run [bold]paw doctor[/bold] to verify.")


@app.command()
def config() -> None:
    """Show current configuration."""
    console.print("[bold]PAW Configuration[/bold]\n")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Setting")
    table.add_column("Value")

    config_items = [
        ("PAW Home", str(settings.paw_home)),
        ("Database", str(settings.db_path)),
        ("Skills Dir", str(settings.skills_path)),
        ("Knowledge Dir", str(settings.knowledge_path)),
        ("Max Context Tokens", str(settings.max_context_tokens)),
        ("Log Level", settings.log_level),
        ("Log Format", settings.log_format),
        ("Default Policy", settings.default_policy_mode),
    ]

    for key, value in config_items:
        table.add_row(key, value)

    console.print(table)


@app.command()
def profiles(
    name: str = typer.Argument(None, help="Profile name to show details for"),
) -> None:
    """List or show execution profiles (Phase 10 K)."""
    if name:
        from ..core.execution_profile import get_execution_profile
        try:
            profile = get_execution_profile(name)
        except Exception:
            console.print(f"[red]Unknown profile:[/red] {name}")
            raise typer.Exit(code=1) from None

        console.print(f"[bold]Execution Profile:[/bold] {profile.name}\n")
        console.print(f"Description: {profile.description}")
        console.print(f"Autonomy Profile: {profile.autonomy_profile.value}")
        console.print(f"Privacy Preference: {profile.privacy_preference.value}")
        console.print(f"Cost Priority: {profile.cost_priority}")
        console.print(f"Latency Priority: {profile.latency_priority}")
        console.print(f"Skill Risk Tolerance: {profile.skill_risk_tolerance.value}")
        console.print(f"Skill Confidence Threshold: {profile.skill_confidence_threshold}")
        console.print(f"Progressive Loading: {profile.progressive_loading}")
        console.print(f"Max Parallelism: {profile.max_parallelism}")
        if profile.skill_categories:
            console.print(f"Skill Categories: {', '.join(profile.skill_categories)}")
        if profile.preferred_models:
            console.print(f"Preferred Models: {', '.join(profile.preferred_models)}")

        # Show resolved autonomy budget
        budget = profile.resolved_autonomy_budget()
        console.print("\n[bold]Resolved Autonomy Budget:[/bold]")
        console.print(f"  Max Decisions: {budget.max_decisions}")
        console.print(f"  Max Model Calls: {budget.max_model_calls}")
        console.print(f"  Max Tool Calls: {budget.max_tool_calls}")
        console.print(f"  Max Iterations: {budget.max_iterations}")
        console.print(f"  Max Wall Time (s): {budget.max_wall_time_seconds}")
        return

    # List all profiles
    from ..core.execution_profile import list_execution_profiles
    console.print("[bold]Available Execution Profiles:[/bold]\n")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Name")
    table.add_column("Autonomy")
    table.add_column("Privacy")
    table.add_column("Risk")
    table.add_column("Parallelism")

    for pname in list_execution_profiles():
        from ..core.execution_profile import get_execution_profile
        p = get_execution_profile(pname)
        table.add_row(
            p.name,
            p.autonomy_profile.value,
            p.privacy_preference.value,
            p.skill_risk_tolerance.value,
            str(p.max_parallelism),
        )

    console.print(table)
    console.print("\nRun [bold]paw profiles <name>[/bold] to see full details.")


async def _chat_async(
    *,
    message: str | None,
    session_id: str | None,
    provider: str,
    json_output: bool,
    approve: bool,
    resume: bool,
    cancel: bool,
    show_status: bool,
    show_history: bool,
) -> None:
    from ..application.chat import ChatService

    service = ChatService(provider_mode=provider)
    try:
        session = await service.open(session_id)
        if approve:
            _print_chat_reply(await service.approve(), json_output)
            return
        if resume:
            _print_chat_reply(await service.resume(), json_output)
            return
        if cancel:
            _print_chat_reply(await service.cancel(), json_output)
            return
        if show_status:
            _print_chat_status(await service.status(), json_output)
            return
        if show_history:
            _print_chat_history(await service.history(), json_output)
            return
        if message is not None:
            _print_chat_reply(await service.send(message), json_output)
            return

        console.print("[bold]PAW Chat[/bold]")
        console.print(
            f"[dim]session={session.session_id} | provider={provider} | "
            "gõ /help để xem lệnh[/dim]"
        )
        while True:
            try:
                user_input = console.input("[bold green]you>[/bold green] ").strip()
            except (EOFError, KeyboardInterrupt):
                console.print()
                break
            if not user_input:
                continue
            command, _, argument = user_input.partition(" ")
            if command in {"/exit", "/quit"}:
                break
            if command == "/help":
                console.print(
                    "/status  /history  /approve [id]  /resume  /cancel  /exit"
                )
                continue
            if command == "/status":
                _print_chat_status(await service.status())
                continue
            if command == "/history":
                _print_chat_history(await service.history())
                continue
            if command == "/approve":
                _print_chat_reply(await service.approve(argument or None), False)
                continue
            if command == "/resume":
                _print_chat_reply(await service.resume(), False)
                continue
            if command == "/cancel":
                _print_chat_reply(await service.cancel(), False)
                break
            if command.startswith("/"):
                console.print(f"[yellow]Lệnh không hợp lệ: {command}. Dùng /help.[/yellow]")
                continue
            _print_chat_reply(await service.send(user_input), False)
    finally:
        await service.close()
        await db.close()


@app.command()
def chat(
    message: str | None = typer.Option(
        None,
        "--message",
        "-m",
        help="Send one message and exit instead of opening the REPL.",
    ),
    session_id: str | None = typer.Option(
        None,
        "--session",
        "-s",
        help="Resume a durable chat session.",
    ),
    provider: str = typer.Option(
        "local",
        "--provider",
        help="Model provider mode: local, auto, or ollama.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
    approve: bool = typer.Option(False, "--approve", help="Approve and resume the pending operation."),
    resume: bool = typer.Option(False, "--resume", help="Resume an already-approved operation."),
    cancel: bool = typer.Option(False, "--cancel", help="Cancel this chat session."),
    show_status: bool = typer.Option(False, "--status", help="Show durable chat/runtime status."),
    show_history: bool = typer.Option(False, "--history", help="Show the durable transcript."),
) -> None:
    """Chat through the full PAW runtime with policy, approval and resume."""
    modes = [
        message is not None,
        approve,
        resume,
        cancel,
        show_status,
        show_history,
    ]
    if sum(modes) > 1:
        console.print("[red]Choose only one action: message/approve/resume/cancel/status/history.[/red]")
        raise typer.Exit(code=2)
    try:
        asyncio.run(
            _chat_async(
                message=message,
                session_id=session_id,
                provider=provider,
                json_output=json_output,
                approve=approve,
                resume=resume,
                cancel=cancel,
                show_status=show_status,
                show_history=show_history,
            )
        )
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from None


if __name__ == "__main__":
    app()
