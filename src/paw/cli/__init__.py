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


if __name__ == "__main__":
    app()
