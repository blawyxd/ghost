
from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ghost.modules.system import check_updates, disk_summary, find_large_files
from ghost.modules.commands import SAVED_COMMANDS
from ghost.modules.ship import ship_project

app = typer.Typer(
    invoke_without_command=True,
    no_args_is_help=False,
    help="Your little Linux companion."
)

console = Console()


@app.callback()
def home(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        console.print()
        console.print(Panel(
            "[bold white]◈ ghost.[/bold white]\n"
            "[dim]your little Linux companion[/dim]\n\n"
            "  ghost updates   Check updates\n"
            "  ghost disk      View disk usage\n"
            "  ghost large     Find large files\n"
            "  ghost vault     Saved commands\n"
            "  ghost ship      Publish project (maintainer)\n"
            "  ghost help      Show help",
            border_style="white",
            padding=(1, 2)
        ))


@app.command()
def updates():
    """Check available system updates."""
    console.print("\n[bold]◈ System updates[/bold]\n")
    result = check_updates()

    if result is None:
        console.print("[red]Couldn't check updates.[/red]")
    elif not result:
        console.print("[green]System is up to date.[/green]")
    else:
        console.print(f"[yellow]{len(result)} updates available:[/yellow]")
        for item in result:
            console.print(f"  • {item}")


@app.command()
def disk():
    """Show disk usage."""
    console.print("\n[bold]◈ Disk overview[/bold]\n")
    for line in disk_summary():
        console.print(line)


@app.command()
def large():
    """Find large files in your home directory."""
    console.print("\n[bold]◈ Large files[/bold]\n")
    console.print("[dim]Scanning...[/dim]")

    files = find_large_files()

    if not files:
        console.print("[green]No files over 500 MB found.[/green]")
        return

    table = Table()
    table.add_column("Size", justify="right")
    table.add_column("File")

    for size, path in files:
        table.add_row(f"{size:.2f} GB", path)

    console.print(table)


@app.command()
def vault():
    """Show saved commands."""
    console.print("\n[bold]◈ Command vault[/bold]\n")

    for name, command, description in SAVED_COMMANDS:
        console.print(f"[bold]{name}[/bold]")
        console.print(f"  [cyan]{command}[/cyan]")
        console.print(f"  [dim]{description}[/dim]\n")


@app.command("help")
def show_help():
    """Show available commands."""
    console.print("\n[bold]◈ ghost. commands[/bold]\n")

    commands = [
        ("ghost", "Home screen"),
        ("ghost updates", "Check system updates"),
        ("ghost disk", "View disk usage"),
        ("ghost large", "Find large files"),
        ("ghost vault", "View saved commands"),
        ("ghost ship", "Publish project (maintainer only)"),
        ("ghost help", "Show help"),
    ]

    for command, description in commands:
        console.print(f"[bold white]{command:<42}[/bold white] {description}")


@app.command()
def ship():
    """Check, build and publish Ghost. Maintainer only."""
    ship_project(console)


def cli():
    app()


if __name__ == "__main__":
    cli()
