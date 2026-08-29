"""
PAW CLI — Command line interface for Personal Agent Workstation.
"""

from __future__ import annotations

import asyncio

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


if __name__ == "__main__":
    app()
