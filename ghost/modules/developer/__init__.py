
from __future__ import annotations

import importlib.metadata
import shutil
import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table


TOOLS = {
    "Python": ["python", "--version"],
    "Git": ["git", "--version"],
    "Node.js": ["node", "--version"],
    "npm": ["npm", "--version"],
    "pnpm": ["pnpm", "--version"],
    "Bun": ["bun", "--version"],
    "Rust": ["rustc", "--version"],
    "Cargo": ["cargo", "--version"],
    "Go": ["go", "version"],
    "Java": ["java", "-version"],
    "GCC": ["gcc", "--version"],
    "Clang": ["clang", "--version"],
    "CMake": ["cmake", "--version"],
    "Docker": ["docker", "--version"],
    "Podman": ["podman", "--version"],
    "uv": ["uv", "--version"],
}


def run_command(command: list[str], timeout: int = 5) -> str | None:
    if not shutil.which(command[0]):
        return None

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

        if result.returncode != 0:
            return None

        output = result.stdout.strip() or result.stderr.strip()
        return output.splitlines()[0] if output else None

    except (OSError, subprocess.TimeoutExpired):
        return None


def dev_report(console: Console) -> None:
    console.print("\n[bold white]◈ ghost. / developer[/bold white]")
    console.print("[dim]Development environment overview[/dim]\n")

    table = Table(show_header=True, header_style="bold white")
    table.add_column("Tool")
    table.add_column("Version / Status")

    available = 0

    for name, command in TOOLS.items():
        version = run_command(command)

        if version:
            table.add_row(name, f"[green]{version}[/green]")
            available += 1
        else:
            table.add_row(name, "[dim]Not installed / unavailable[/dim]")

    console.print(table)
    console.print(
        f"\n[cyan]{available}/{len(TOOLS)}[/cyan] development tools detected."
    )


def git_report(console: Console, directory: Path | None = None) -> None:
    target = (directory or Path.cwd()).expanduser().resolve()

    console.print("\n[bold white]◈ ghost. / git[/bold white]")
    console.print("[dim]Repository inspection[/dim]\n")

    if not target.exists() or not target.is_dir():
        console.print("[red]Directory does not exist.[/red]")
        return

    def git(*args: str) -> str | None:
        return run_git(target, list(args))

    root = git("rev-parse", "--show-toplevel")

    if not root:
        console.print(f"[yellow]No Git repository found in {target}[/yellow]")
        return

    branch = git("branch", "--show-current") or "Detached HEAD"
    commit = git("log", "-1", "--format=%h %s") or "No commits yet"
    status = git("status", "--short", "--branch") or "Clean"

    console.print(f"[bold]Repository:[/bold] {root}")
    console.print(f"[bold]Branch:[/bold] [cyan]{branch}[/cyan]")
    console.print(f"[bold]Latest commit:[/bold] {commit}\n")

    table = Table(show_header=False, box=None)
    table.add_row("Working tree", status)
    console.print(table)

    changes = git("status", "--short")

    if changes:
        console.print("\n[bold]Changed files[/bold]")

        for line in changes.splitlines()[:30]:
            console.print(f"  {line}")

        remaining = len(changes.splitlines()) - 30

        if remaining > 0:
            console.print(f"[dim]...and {remaining} more[/dim]")
    else:
        console.print("\n[green]Working tree is clean.[/green]")

    history = git("log", "-5", "--oneline")

    if history:
        console.print("\n[bold]Recent commits[/bold]")

        for line in history.splitlines():
            console.print(f"  {line}")


def run_git(directory: Path, arguments: list[str]) -> str | None:
    if not shutil.which("git"):
        return None

    try:
        result = subprocess.run(
            ["git", "-C", str(directory), *arguments],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        if result.returncode != 0:
            return None

        return result.stdout.strip()

    except (OSError, subprocess.TimeoutExpired):
        return None


def env_report(console: Console, directory: Path | None = None) -> None:
    target = (directory or Path.cwd()).expanduser().resolve()

    console.print("\n[bold white]◈ ghost. / environment[/bold white]")
    console.print("[dim]Python and project environment inspection[/dim]\n")

    console.print(f"[bold]Directory:[/bold] {target}")
    console.print(f"[bold]Python executable:[/bold] {sys.executable}")
    console.print(f"[bold]Python version:[/bold] {sys.version.split()[0]}")
    console.print(
        f"[bold]Virtual environment:[/bold] "
        f"{'Yes' if sys.prefix != sys.base_prefix else 'No'}"
    )

    table = Table(title="Project files")
    table.add_column("File")
    table.add_column("Status")

    project_files = [
        "pyproject.toml",
        "requirements.txt",
        "Pipfile",
        "poetry.lock",
        "uv.lock",
        "setup.py",
        "setup.cfg",
        ".python-version",
        ".venv",
        "venv",
    ]

    for name in project_files:
        exists = (target / name).exists()

        table.add_row(
            name,
            "[green]Found[/green]" if exists else "[dim]Not found[/dim]",
        )

    console.print()
    console.print(table)

    if sys.prefix != sys.base_prefix:
        console.print(
            f"\n[green]Active environment:[/green] {sys.prefix}"
        )


def deps_report(console: Console) -> None:
    console.print("\n[bold white]◈ ghost. / dependencies[/bold white]")
    console.print("[dim]Installed Python packages[/dim]\n")

    packages = sorted(
        importlib.metadata.distributions(),
        key=lambda package: (
            package.metadata.get("Name") or ""
        ).lower(),
    )

    table = Table(show_header=True, header_style="bold white")
    table.add_column("Package")
    table.add_column("Version")

    for package in packages:
        name = package.metadata.get("Name") or "Unknown"
        version = package.version or "Unknown"
        table.add_row(name, version)

    console.print(table)
    console.print(f"\n[cyan]{len(packages)}[/cyan] installed packages.")

    console.print(
        "\n[dim]This lists installed packages only. "
        "It does not check for updates or change dependencies.[/dim]"
    )


def explain_project(console: Console) -> None:
    console.print(
        Panel(
            "[bold cyan]Ghost Developer Tools[/bold cyan]\n\n"
            "ghost dev       Inspect installed development tools\n"
            "ghost git       Inspect the current Git repository\n"
            "ghost env       Inspect the current Python environment\n"
            "ghost deps      List installed Python packages\n\n"
            "[dim]All developer commands are read-only.[/dim]",
            title="◈ ghost.",
            border_style="blue",
        )
    )
