from __future__ import annotations

import getpass
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = Path.home() / ".config/ghost/maintainer.json"

BLOCKED_FILES = {
    ".env",
    "credentials.json",
    "secrets.json",
    "id_rsa",
    "id_ed25519",
}


def check_maintainer(console: Console) -> bool:
    """Check whether this machine is registered as the maintainer."""
    try:
        if not CONFIG_PATH.is_file():
            raise ValueError("Maintainer configuration not found.")

        metadata = CONFIG_PATH.stat()

        if metadata.st_uid != os.getuid():
            raise ValueError("Maintainer configuration has the wrong owner.")

        if stat.S_IMODE(metadata.st_mode) & 0o077:
            raise ValueError("Configuration permissions are too open.")

        config = json.loads(CONFIG_PATH.read_text())
        username = config.get("username")
        machine_id = config.get("machine_id")
        current_machine = Path("/etc/machine-id").read_text().strip()

        if not username or not machine_id:
            raise ValueError("Maintainer configuration is incomplete.")

        if username != getpass.getuser():
            raise ValueError("Incorrect Linux user.")

        if machine_id != current_machine:
            raise ValueError("This machine is not authorised to ship Ghost.")

        return True

    except (OSError, ValueError, json.JSONDecodeError) as error:
        console.print(f"[red]Ship access denied: {error}[/red]")
        return False


def run_step(
    console: Console,
    label: str,
    command: list[str],
    cwd: Path = ROOT,
) -> bool:
    console.print(f"\n[bold]◈ {label}[/bold]")
    console.print(f"[dim]$ {' '.join(command)}[/dim]\n")

    try:
        result = subprocess.run(command, cwd=cwd, check=False)
    except FileNotFoundError:
        console.print(f"[red]Required command not found: {command[0]}[/red]")
        return False

    if result.returncode != 0:
        console.print(f"\n[red]Failed: {label}[/red]")
        return False

    console.print(f"[green]✓ {label} passed[/green]")
    return True


def git_output(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        return ""

    return result.stdout.strip()


def unsafe_files(files: list[str]) -> list[str]:
    blocked = []

    for filename in files:
        name = Path(filename).name.lower()

        if (
            name in BLOCKED_FILES
            or name.endswith((".pem", ".p12", ".pfx", ".key"))
            or name.startswith(("id_rsa", "id_ed25519"))
            or (name.startswith(".env.") and name != ".env.example")
        ):
            blocked.append(filename)

    return blocked


def ship_project(console: Console) -> None:
    if not check_maintainer(console):
        raise typer.Exit(1)

    console.print()
    console.print(Panel(
        "[bold white]◈ ghost. / ship[/bold white]\n"
        "[dim]Check, build, commit and publish.[/dim]",
        border_style="white",
        padding=(1, 2),
    ))

    for program in ("git", "npm"):
        if not shutil.which(program):
            console.print(f"[red]{program} is not installed.[/red]")
            raise typer.Exit(1)

    if git_output("rev-parse", "--show-toplevel") != str(ROOT):
        console.print("[red]This directory is not a Git repository.[/red]")
        raise typer.Exit(1)

    branch = git_output("branch", "--show-current")

    if branch != "main":
        console.print(f"[red]You're on '{branch}', not 'main'.[/red]")
        console.print("Switch to main before shipping.")
        raise typer.Exit(1)

    if not git_output("remote", "get-url", "origin"):
        console.print("[red]No GitHub origin remote is configured.[/red]")
        raise typer.Exit(1)

    console.print("\n[bold]1. Checking project[/bold]")

    checks = [
        (
            "Python syntax",
            [sys.executable, "-m", "compileall", "-q", "main.py", "ghost"],
            ROOT,
        ),
        (
            "Python package installation",
            [sys.executable, "-m", "pip", "install", "-e", "."],
            ROOT,
        ),
        ("Ghost CLI", ["ghost", "--help"], ROOT),
        ("Ghost help command", ["ghost", "help"], ROOT),
        ("Website dependencies", ["npm", "ci"], ROOT / "website"),
        ("Astro website build", ["npm", "run", "build"], ROOT / "website"),
        ("Git whitespace check", ["git", "diff", "--check"], ROOT),
    ]

    for label, command, directory in checks:
        if not run_step(console, label, command, directory):
            console.print(
                "\n[yellow]Checks failed. Nothing has been committed or pushed.[/yellow]"
            )
            raise typer.Exit(1)

    console.print("\n[bold]2. Preparing changes[/bold]")

    result = subprocess.run(
        ["git", "add", "-A"],
        cwd=ROOT,
        check=False,
    )

    if result.returncode != 0:
        console.print("[red]Couldn't stage changes.[/red]")
        raise typer.Exit(1)

    staged = git_output("diff", "--cached", "--name-only").splitlines()

    if not staged:
        console.print("[green]Everything is already committed.[/green]")
        return

    blocked = unsafe_files(staged)

    if blocked:
        console.print("[red]Potentially sensitive files are staged:[/red]")

        for filename in blocked:
            console.print(f"  • {filename}")

        console.print("[yellow]Inspect and unstage these files before shipping.[/yellow]")
        raise typer.Exit(1)

    if not run_step(
        console,
        "Staged changes check",
        ["git", "diff", "--cached", "--check"],
    ):
        raise typer.Exit(1)

    console.print("\n[bold]Files to publish:[/bold]")

    for filename in staged:
        console.print(f"  [cyan]+[/cyan] {filename}")

    console.print()

    if not typer.confirm("Continue and publish these changes?", default=False):
        console.print("[yellow]Cancelled. Your changes remain staged.[/yellow]")
        return

    message = typer.prompt("Commit message", default="Update Ghost")

    if not run_step(
        console,
        "Create commit",
        ["git", "commit", "-m", message],
    ):
        raise typer.Exit(1)

    if not run_step(
        console,
        "Push to GitHub",
        ["git", "push", "origin", "main"],
    ):
        console.print(
            "[yellow]Local commit remains. Fix the push issue and retry.[/yellow]"
        )
        raise typer.Exit(1)

    console.print()
    console.print(Panel(
        "[bold green]Successfully pushed to GitHub.[/bold green]\n\n"
        "GitHub Actions will run your checks.\n"
        "Cloudflare Pages should automatically deploy the website.",
        border_style="green",
        padding=(1, 2),
    ))

    if shutil.which("gh"):
        authenticated = subprocess.run(
            ["gh", "auth", "status"],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode == 0

        if authenticated and typer.confirm(
            "Wait for GitHub Actions to finish?",
            default=True,
        ):
            subprocess.run(
                ["gh", "run", "watch", "--exit-status"],
                cwd=ROOT,
                check=False,
            )

    console.print(
        "\n[dim]Check Cloudflare Workers & Pages for deployment status.[/dim]"
    )
