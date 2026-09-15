"""
PAW CLI — Command line interface for Personal Agent Workstation.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import sys
from typing import Any

import structlog
import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from .. import __version__
from ..core.config import settings
from ..core.storage import db


def _sanitize_text(text: str) -> str:
    """Replace lone UTF-16 surrogates that can arise from mis-decoded terminal
    or command-line input, so printing/storing never raises
    UnicodeEncodeError. A correctly decoded character is left untouched.
    """
    if not text:
        return text
    return "".join("\ufffd" if 0xD800 <= ord(ch) <= 0xDFFF else ch for ch in text)


# Ensure output streams tolerate any stray surrogate so a mis-encoded terminal
# argument never crashes the CLI (it degrades to the replacement character).
for _stream in (sys.stdout, sys.stderr):
    with contextlib.suppress(AttributeError, ValueError, OSError):
        _stream.reconfigure(encoding="utf-8", errors="replace")

app = typer.Typer(
    name="paw",
    help="PAW — Personal Agent Workstation",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
)

console = Console()


# ── Beta subcommand group ──
beta_app = typer.Typer(name="beta", help="Beta: daily engineering-partner profiles", no_args_is_help=True)
app.add_typer(beta_app, name="beta")


@beta_app.command("profiles")
def beta_profiles(
    name: str = typer.Argument(None, help="Beta profile name to show (analyze|ideate|change|review)"),
) -> None:
    """List or show the four daily beta profiles."""
    from ..core.beta_profiles import BETA_PROFILES, get_beta_profile, list_beta_profiles

    if name:
        profile = get_beta_profile(name)
        if profile is None:
            console.print(f"[red]Unknown beta profile:[/red] {name}")
            console.print(f"Available: {', '.join(list_beta_profiles())}")
            raise typer.Exit(code=1)

        console.print(f"[bold]Beta Profile:[/bold] {profile.name}\n")
        console.print(f"Description: {profile.description}")
        console.print(f"Side Effect Policy: {profile.side_effect_policy.value}")
        ep = profile.execution_profile
        console.print(f"Autonomy Profile: {ep.autonomy_profile.value}")
        console.print(f"Privacy Preference: {ep.privacy_preference.value}")
        console.print(f"Skill Risk Tolerance: {ep.skill_risk_tolerance.value}")
        if profile.allowed_capabilities is not None:
            console.print(f"Allowed Capabilities: {len(profile.allowed_capabilities)} (read-only subset)")
        if profile.gated_capabilities:
            console.print(f"Gated Capabilities: {len(profile.gated_capabilities)} (require approval)")
    else:
        table = Table(title="PAW Beta Profiles")
        table.add_column("Profile", style="cyan")
        table.add_column("Policy", style="yellow")
        table.add_column("Description")
        for _pname, profile in BETA_PROFILES.items():
            table.add_row(
                profile.name,
                profile.side_effect_policy.value,
                profile.description,
            )
        console.print(table)


def _print_chat_reply(reply: Any, json_output: bool) -> None:
    if json_output:
        typer.echo(json.dumps(reply.to_dict(), ensure_ascii=False))
        return
    if reply.thinking:
        console.print(f"[dim italic]paw (thinking):[/dim italic] {escape(_sanitize_text(reply.thinking))}")
    console.print(f"[bold cyan]paw>[/bold cyan] {escape(_sanitize_text(reply.content))}")
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
        console.print(f"[{color}]{item.role.value}>[/{color}] {escape(_sanitize_text(item.content))}")


def _print_inspection(title: str, value: Any, json_output: bool = False) -> None:
    """Render an inspect/explain payload for humans or scripts."""
    if json_output:
        typer.echo(json.dumps(value, ensure_ascii=False, default=str))
        return
    console.print(f"[bold cyan]{title}[/bold cyan]")
    console.print_json(data=value)


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
    workspace: str,
    json_output: bool,
    approve: bool,
    resume: bool,
    cancel: bool,
    show_status: bool,
    show_history: bool,
    show_plan: bool,
    show_why: bool,
    show_ledger: bool,
    show_checkpoint: bool,
    show_policy: bool,
    show_skills: bool,
    show_artifacts: bool,
    quiet: bool = False,
    debug: bool = False,
) -> None:
    from ..application.chat import ChatService

    service = ChatService(provider_mode=provider, workspace_root=workspace)
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
        if show_plan:
            _print_inspection("Plan", await service.plan(), json_output)
            return
        if show_why:
            _print_inspection("Why", await service.explain(), json_output)
            return
        if show_ledger:
            _print_inspection("Ledger", await service.ledger(), json_output)
            return
        if show_checkpoint:
            _print_inspection("Checkpoint", await service.checkpoint(), json_output)
            return
        if show_policy:
            _print_inspection("Policy", await service.policy(), json_output)
            return
        if show_skills:
            _print_inspection("Skills", await service.skills(), json_output)
            return
        if show_artifacts:
            _print_inspection("Artifacts", await service.artifacts(), json_output)
            return
        if message is not None:
            _print_chat_reply(await service.send(_sanitize_text(message)), json_output)
            return

        console.print("[bold]PAW Chat[/bold]")
        console.print(
            f"[dim]session={session.session_id} | provider={provider} | "
            f"workspace={service.workspace_root} | "
            "gõ /help để xem lệnh[/dim]"
        )
        while True:
            try:
                user_input = _sanitize_text(
                    console.input("[bold green]you>[/bold green] ").strip()
                )
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
                    "/status  /history  /plan  /why  /ledger  /checkpoint  "
                    "/policy  /skills  /artifacts  /approve [id]  /resume  "
                    "/cancel  /exit"
                )
                continue
            if command == "/status":
                _print_chat_status(await service.status())
                continue
            if command == "/history":
                _print_chat_history(await service.history())
                continue
            if command == "/plan":
                _print_inspection("Plan", await service.plan())
                continue
            if command == "/why":
                _print_inspection("Why", await service.explain())
                continue
            if command == "/ledger":
                _print_inspection("Ledger", await service.ledger())
                continue
            if command == "/checkpoint":
                _print_inspection("Checkpoint", await service.checkpoint())
                continue
            if command == "/policy":
                _print_inspection("Policy", await service.policy())
                continue
            if command == "/skills":
                _print_inspection("Skills", await service.skills())
                continue
            if command == "/artifacts":
                _print_inspection("Artifacts", await service.artifacts())
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
        "auto",
        "--provider",
        help="Model provider mode: auto (try Ollama, fall back to local), local (offline echo stand-in), or ollama.",
    ),
    workspace: str = typer.Option(
        ".",
        "--workspace",
        help="Workspace boundary for local filesystem operations.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
    approve: bool = typer.Option(False, "--approve", help="Approve and resume the pending operation."),
    resume: bool = typer.Option(False, "--resume", help="Resume an already-approved operation."),
    cancel: bool = typer.Option(False, "--cancel", help="Cancel this chat session."),
    show_status: bool = typer.Option(False, "--status", help="Show durable chat/runtime status."),
    show_history: bool = typer.Option(False, "--history", help="Show the durable transcript."),
    show_plan: bool = typer.Option(False, "--plan", help="Show the latest proposed operation."),
    show_why: bool = typer.Option(False, "--why", help="Explain the latest runtime decisions."),
    show_ledger: bool = typer.Option(False, "--ledger", help="Show the current task ledger."),
    show_checkpoint: bool = typer.Option(
        False, "--checkpoint", help="Show the latest checkpoint summary."
    ),
    show_policy: bool = typer.Option(False, "--policy", help="Show policy and approval state."),
    show_skills: bool = typer.Option(False, "--skills", help="Show skill/context selection."),
    show_artifacts: bool = typer.Option(False, "--artifacts", help="Show task artifacts."),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress INFO logs (only show errors)."),
    debug: bool = typer.Option(False, "--debug", help="Show DEBUG-level logs for troubleshooting."),
) -> None:
    """Chat through the full PAW runtime with policy, approval and resume."""
    modes = [
        message is not None,
        approve,
        resume,
        cancel,
        show_status,
        show_history,
        show_plan,
        show_why,
        show_ledger,
        show_checkpoint,
        show_policy,
        show_skills,
        show_artifacts,
    ]
    if sum(modes) > 1:
        console.print("[red]Choose only one chat action or inspection flag.[/red]")
        raise typer.Exit(code=2)

    # Configure structured logging based on flags (Option B: stderr separation)
    # By default in REPL mode: only WARNING+ goes to stderr, keeping stdout clean.
    # configure_logging() sets cache_logger_on_first_use=False in core/logging.py.
    from ..core.logging import configure_logging as _configure_logging

    if debug:
        _log_level = logging.DEBUG
    elif quiet:
        _log_level = logging.ERROR
    else:
        _log_level = logging.WARNING
    _configure_logging(_log_level)

    try:
        asyncio.run(
            _chat_async(
                message=message,
                session_id=session_id,
                provider=provider,
                workspace=workspace,
                json_output=json_output,
                approve=approve,
                resume=resume,
                cancel=cancel,
                show_status=show_status,
                show_history=show_history,
                show_plan=show_plan,
                show_why=show_why,
                show_ledger=show_ledger,
                show_checkpoint=show_checkpoint,
                show_policy=show_policy,
                show_skills=show_skills,
                show_artifacts=show_artifacts,
                quiet=quiet,
                debug=debug,
            )
        )
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from None


@app.command()
def tui(
    session_id: str | None = typer.Option(
        None,
        "--session",
        "-s",
        help="Resume a durable chat session.",
    ),
    provider: str = typer.Option(
        "auto",
        "--provider",
        help="Model provider mode: auto (try Ollama, fall back to local), local (offline), or ollama.",
    ),
    workspace: str = typer.Option(
        ".",
        "--workspace",
        help="Workspace boundary for local filesystem operations.",
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress INFO logs (only show errors)."),
    debug: bool = typer.Option(False, "--debug", help="Show DEBUG-level logs."),
) -> None:
    """Launch the interactive Textual TUI with 3-panel layout and token streaming."""
    from ..core.logging import configure_logging as _configure_logging

    if debug:
        _log_level = logging.DEBUG
    elif quiet:
        _log_level = logging.ERROR
    else:
        _log_level = logging.WARNING
    _configure_logging(_log_level)

    from ..tui import run_tui

    try:
        run_tui(
            provider_mode=provider,
            workspace=workspace,
            session_id=session_id,
        )
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from None


@beta_app.command("inspect")
def beta_inspect(
    kind: str = typer.Argument(..., help="What to inspect: memory, skills, routing, ledger, context"),
    task_id: str = typer.Option(None, help="Task ID to inspect (for ledger/context)"),
    limit: int = typer.Option(20, help="Max entries to show"),
) -> None:
    """Inspect runtime state: memory, skills, routing, ledger, context."""
    asyncio.run(_do_beta_inspect(kind, task_id, limit))


async def _do_beta_inspect(kind: str, task_id: str | None, limit: int) -> None:
    from ..core.ledger import TaskLedger

    if kind == "memory":
        from ..core.memory import MemoryRetriever
        try:
            await db.initialize()
            retriever = MemoryRetriever()
            records = await retriever.get_recent(limit=limit)
        except Exception as exc:
            console.print(f"[yellow]Cannot load memory: {exc}[/yellow]")
            return
        if not records:
            console.print("[yellow]No memory records.[/yellow]")
            return
        table = Table(title="PAW Memory Records")
        table.add_column("ID", overflow="fold")
        table.add_column("Content", overflow="fold")
        table.add_column("Relevance", justify="right")
        for r in records:
            table.add_row(
                str(r.id)[:12],
                _sanitize_text(r.content[:80]),
                f"{getattr(r, 'relevance_score', 0):.2f}" if hasattr(r, 'relevance_score') else "—",
            )
        console.print(table)

    elif kind == "skills":
        from ..core.skills import get_skill_fabric
        try:
            fabric = await get_skill_fabric()
            skills = fabric.list_skills()
        except Exception as exc:
            console.print(f"[yellow]Cannot load skills: {exc}[/yellow]")
            return
        if not skills:
            console.print("[yellow]No skills registered.[/yellow]")
            return
        table = Table(title="PAW Skills")
        table.add_column("Name", style="cyan")
        table.add_column("Category")
        table.add_column("Risk")
        table.add_column("Capabilities")
        for s in skills:
            caps = ", ".join(c.value for c in getattr(s, "capabilities", [])) if hasattr(s, "capabilities") else ""
            table.add_row(
                s.name,
                s.category,
                s.risk.value if hasattr(s, "risk") and hasattr(s.risk, "value") else str(getattr(s, "risk", "")),
                caps,
            )
        console.print(table)

    elif kind == "routing":
        from ..core.model_router import ProviderRegistry
        try:
            registry = ProviderRegistry()
            models = await registry.discover_models()
        except Exception as exc:
            console.print(f"[yellow]Cannot load models: {exc}[/yellow]")
            return
        if not models:
            console.print("[yellow]No models registered.[/yellow]")
            return
        table = Table(title="PAW Model Routing")
        table.add_column("Model", style="cyan")
        table.add_column("Provider")
        table.add_column("Roles")
        table.add_column("Local")
        for m in models:
            roles = ", ".join(m.roles) if hasattr(m, "roles") else ""
            local = "yes" if getattr(m, "local", False) else "no"
            table.add_row(m.name, getattr(m, "provider", ""), roles, local)
        console.print(table)

    elif kind == "ledger":
        if not task_id:
            console.print("[red]task_id is required for ledger inspection.[/red]")
            raise typer.Exit(code=1)
        try:
            await db.initialize()
            events = await TaskLedger.get_events(task_id, limit=limit)
        except Exception as exc:
            console.print(f"[yellow]Cannot load ledger: {exc}[/yellow]")
            return
        if not events:
            console.print(f"[yellow]No events for task: {task_id}[/yellow]")
            return
        table = Table(title=f"PAW Ledger: {task_id}")
        table.add_column("Timestamp")
        table.add_column("Event")
        table.add_column("Details")
        for e in events:
            table.add_row(
                str(e.timestamp)[:19] if hasattr(e, "timestamp") else "—",
                e.event_type.value if hasattr(e, "event_type") else "—",
                _sanitize_text(str(e.details)[:80]) if hasattr(e, "details") else "",
            )
        console.print(table)

    elif kind == "context":
        if not task_id:
            console.print("[red]task_id is required for context inspection.[/red]")
            raise typer.Exit(code=1)
        try:
            await db.initialize()
            events = await TaskLedger.get_events(task_id, limit=limit)
            rows = [
                {
                    "op_type": e.event_type.value if hasattr(e, "event_type") else "—",
                    "status": "recorded",
                    "timestamp": e.timestamp.isoformat() if hasattr(e, "timestamp") else "",
                }
                for e in events
            ]
        except Exception as exc:
            console.print(f"[yellow]Cannot load context: {exc}[/yellow]")
            return
        if not rows:
            console.print(f"[yellow]No operations recorded for task: {task_id}[/yellow]")
            return
        table = Table(title=f"PAW Context/Operations: {task_id}")
        table.add_column("Timestamp")
        table.add_column("Op Type")
        table.add_column("Status")
        for r in rows:
            table.add_row(
                r.get("timestamp", "")[:19],
                r.get("op_type", "—"),
                r.get("status", "—"),
            )
        console.print(table)

    else:
        console.print(f"[red]Unknown inspect kind: {kind}[/red]")
        console.print("Available: memory, skills, routing, ledger, context")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
