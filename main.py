
from __future__ import annotations

import inspect
import typer
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ghost.modules.system import (
    check_updates,
    disk_summary,
    find_large_files,
)
from ghost.modules.commands import SAVED_COMMANDS
from ghost.modules.ship import ship_project
from ghost.modules.doctor import doctor_report
from ghost.modules.hardware import hardware_report
from ghost.modules.diagnostics import (
    processes_report,
    services_report,
    network_report,
    ports_report,
    logs_report,
)
from ghost.modules.maintenance import (
    cache_report,
    clean_cache,
    create_backup,
    backups_report,
    restore_backup,
    temp_report,
    orphans_report,
    security_report,
)
from ghost.modules.developer import (
    dev_report,
    git_report,
    env_report,
    deps_report,
)
from ghost.modules.developer.workflows import (
    build_project,
    environment_report,
    git_action_report,
    install_dependencies,
    project_deps_report,
    project_report,
    serve_project,
    test_project,
)
from ghost.modules.learning import (
    learn,
    exercise_command,
    exercises_report,
    learning_settings,
    progress_report,
    glossary,
    cheatsheet,
)
from ghost.modules.learning.projects import projects_report

app = typer.Typer(
    invoke_without_command=True,
    no_args_is_help=False,
    help="Your little Linux companion.",
)

console = Console()


@app.callback()
def home(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        console.print()
        console.print(
            Panel(
                "[bold white]◈ ghost.[/bold white]\n"
                "[dim]your Linux companion[/dim]\n\n"
                "  System health    ghost doctor · ghost hardware · ghost network\n"
                "  Maintenance      ghost cache · ghost clean · ghost backup\n"
                "  Development      ghost project · ghost git · ghost test\n"
                "  Learn Python     ghost learn · ghost exercises · ghost projects\n\n"
                "Run [cyan]ghost help[/cyan] to browse all commands or "
                "[cyan]ghost COMMAND --help[/cyan] for command options.",
                border_style="white",
                padding=(1, 2),
            )
        )


def command_catalog() -> tuple[tuple[str, str], ...]:
    """Build the full help list from Typer's registered commands and docstrings."""
    entries = []
    for info in app.registered_commands:
        callback = info.callback
        if callback is None:
            continue
        name = info.name or callback.__name__.replace("_", "-")
        description = (info.help or inspect.getdoc(callback) or "No description provided.")
        entries.append((name, description.splitlines()[0]))
    return tuple(entries)


@app.command()
def doctor():
    """Diagnose common Linux system problems."""
    doctor_report(console)


@app.command()
def hardware():
    """Show detailed hardware information."""
    hardware_report(console)


@app.command()
def processes():
    """View running processes."""
    processes_report(console)


@app.command()
def services():
    """Inspect systemd services."""
    services_report(console)


@app.command()
def network():
    """Inspect network interfaces and connectivity."""
    network_report(console)


@app.command()
def ports():
    """Show listening network ports."""
    ports_report(console)


@app.command()
def logs():
    """Show recent system journal entries."""
    logs_report(console)


@app.command()
def cache():
    """Inspect user cache usage."""
    cache_report(console)


@app.command()
def clean():
    """Safely clean user cache contents."""
    clean_cache(console)


@app.command()
def backup():
    """Create a local configuration backup."""
    create_backup(console)


@app.command()
def backups():
    """List local configuration backups."""
    backups_report(console)


@app.command("restore-backup")
def restore_configuration_backup(
    archive_name: str = typer.Argument(..., help="Filename shown by `ghost backups`"),
):
    """Restore missing configuration files without overwriting existing files."""
    restore_backup(console, archive_name)


@app.command("temp")
def temporary_files():
    """Inspect temporary storage without deleting anything."""
    temp_report(console)


@app.command()
def orphans():
    """Inspect unneeded pacman dependencies without removing them."""
    orphans_report(console)


@app.command()
def security():
    """Run basic security checks."""
    security_report(console)


@app.command()
def dev():
    """Detect installed development tools."""
    dev_report(console)


@app.command()
def git(action: str = typer.Argument("status", help="status, diff, log, branches, or remotes")):
    """Inspect Git status or common read-only repository details."""
    git_action_report(console, action.lower())


@app.command()
def env():
    """Inspect the current Python environment."""
    env_report(console)


@app.command()
def deps():
    """List installed Python dependencies."""
    deps_report(console)


@app.command()
def project(directory: Path | None = typer.Argument(None, help="Directory to inspect (defaults to the current directory)")):
    """Detect project type, virtual environment, and directory structure."""
    project_report(console, directory)


@app.command("project-deps")
def project_dependencies(directory: Path | None = typer.Argument(None, help="Directory to inspect")):
    """List dependencies declared by the current Python project."""
    project_deps_report(console, directory)


@app.command("install-deps")
def install_project_dependencies(directory: Path | None = typer.Argument(None, help="Directory to inspect")):
    """Review and confirm installation of declared Python dependencies."""
    install_dependencies(console, directory)


@app.command()
def test(directory: Path | None = typer.Argument(None, help="Project directory; defaults to the current directory")):
    """Run the detected project's test suite."""
    test_project(console, directory)


@app.command()
def build(directory: Path | None = typer.Argument(None, help="Project directory; defaults to the current directory")):
    """Build a supported Python, Node.js, or Rust project."""
    build_project(console, directory)


@app.command()
def serve(
    directory: Path | None = typer.Argument(None, help="Project directory; defaults to the current directory"),
    host: str = typer.Option("127.0.0.1", "--host", help="IPv4 address to bind"),
    port: int = typer.Option(8000, "--port", min=1, max=65535, help="Port to listen on"),
    script: str | None = typer.Option(None, "--script", help="Explicit npm script name (defaults to dev or start)"),
):
    """Start a static, Django, or npm development server in the foreground."""
    serve_project(console, directory, host, port, script)


@app.command("vars")
def variables():
    """Check selected environment variable presence without showing values."""
    environment_report(console)


@app.command("learn")
def learn_command(lesson_id: str | None = typer.Argument(None, help="Lesson ID, or omit to browse")):
    """Browse the programming course or open a lesson."""
    learn(console, lesson_id)


@app.command("exercise")
def exercise(
    exercise_id: str = typer.Argument(..., help="Exercise ID"),
    source_file: Path | None = typer.Option(None, "--file", "-f", help="Python file containing your solution"),
    solution: bool = typer.Option(False, "--solution", help="Show the exercise solution"),
    hint: int | None = typer.Option(None, "--hint", min=1, help="Show a hint without submitting an attempt"),
):
    """Write, get a hint for, or reveal a coding exercise (submissions are not sandboxed)."""
    exercise_command(console, exercise_id, source_file, solution, hint)


@app.command("exercises")
def exercises():
    """Browse Python coding exercises and completion status."""
    exercises_report(console)


@app.command("projects")
def learning_projects(
    project_id: str | None = typer.Argument(None, help="Project ID to view"),
    complete_milestone: int | None = typer.Option(None, "--complete-milestone", min=1, help="Mark a milestone complete"),
    review_path: Path | None = typer.Option(None, "--review", help="Read-only structural review of a project directory"),
):
    """Browse projects, track milestones, or review a project directory."""
    projects_report(console, project_id, complete_milestone, review_path)


@app.command()
def learning(mode: str = typer.Argument(..., help="on, off or status")):
    """Configure Learning Game Mode."""
    learning_settings(console, mode.lower())


@app.command()
def progress():
    """Show learning progress."""
    progress_report(console)


@app.command("glossary")
def glossary_command():
    """Show the programming glossary."""
    glossary(console)


@app.command("cheatsheet")
def cheatsheet_command():
    """Show the Python cheatsheet."""
    cheatsheet(console)


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
    table = Table(title="Ghost commands", show_header=True, header_style="bold white")
    table.add_column("Command")
    table.add_column("Description")
    for command, description in command_catalog():
        table.add_row(f"ghost {command}", description)
    console.print(table)
    console.print("Use [cyan]ghost COMMAND --help[/cyan] for command options.")


@app.command()
def ship():
    """Check, build and publish Ghost. Maintainer only."""
    ship_project(console)


def cli():
    app()


if __name__ == "__main__":
    cli()
