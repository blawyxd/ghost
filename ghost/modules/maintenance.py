
from __future__ import annotations

import os
import shutil
import subprocess
import tarfile
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table


CACHE_DIR = Path.home() / ".cache"
BACKUP_DIR = Path.home() / "GhostBackups"


def format_size(size: int) -> str:
    value = float(size)

    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024

    return f"{value:.1f} TB"


def cache_usage() -> tuple[int, int]:
    total = 0
    files = 0

    if not CACHE_DIR.is_dir() or CACHE_DIR.is_symlink():
        return total, files

    for current, dirs, filenames in os.walk(CACHE_DIR, followlinks=False):
        dirs[:] = [
            name for name in dirs
            if not (Path(current) / name).is_symlink()
        ]

        for name in filenames:
            path = Path(current) / name

            if path.is_symlink():
                continue

            try:
                total += path.stat().st_size
                files += 1
            except OSError:
                continue

    return total, files


def cache_report(console: Console) -> None:
    console.print("\n[bold white]◈ ghost. / cache[/bold white]")
    console.print("[dim]User cache overview · Read-only[/dim]\n")

    if not CACHE_DIR.is_dir() or CACHE_DIR.is_symlink():
        console.print("[yellow]User cache directory not found.[/yellow]")
        return

    total, files = cache_usage()

    table = Table()
    table.add_column("Location")
    table.add_column("Files", justify="right")
    table.add_column("Size", justify="right")

    table.add_row(str(CACHE_DIR), str(files), format_size(total))

    console.print(table)
    console.print(f"\n[bold]Total cache size:[/bold] {format_size(total)}")
    console.print("[dim]Nothing was deleted.[/dim]")


def clean_cache(console: Console) -> None:
    console.print("\n[bold white]◈ ghost. / clean[/bold white]")
    console.print("[dim]User cache cleanup[/dim]\n")

    if not CACHE_DIR.is_dir() or CACHE_DIR.is_symlink():
        console.print("[yellow]User cache directory not found.[/yellow]")
        return

    total, files = cache_usage()

    if not files:
        console.print("[green]Your user cache is already empty.[/green]")
        return

    console.print(f"Files found: {files}")
    console.print(f"Space currently used: {format_size(total)}")
    console.print(f"Target: {CACHE_DIR}")
    console.print(
        "\n[yellow]This removes the contents of ~/.cache. "
        "Applications may recreate these files when needed.[/yellow]"
    )

    if not typer.confirm("Delete these cache contents?", default=False):
        console.print("[dim]Cleanup cancelled.[/dim]")
        return

    removed = 0
    errors = 0

    try:
        for item in CACHE_DIR.iterdir():
            try:
                if item.is_symlink() or item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
                else:
                    continue

                removed += 1
            except OSError:
                errors += 1
    except OSError as error:
        console.print(f"[red]Could not access cache directory: {error}[/red]")
        return

    console.print(f"\n[green]Removed {removed} cache item(s).[/green]")

    if errors:
        console.print(f"[yellow]{errors} item(s) could not be removed.[/yellow]")


def create_backup(console: Console) -> None:
    console.print("\n[bold white]◈ ghost. / backup[/bold white]")
    console.print("[dim]Local configuration backup[/dim]\n")

    config_dir = Path.home() / ".config"

    if not config_dir.is_dir() or config_dir.is_symlink():
        console.print("[yellow]No valid ~/.config directory found.[/yellow]")
        return

    console.print(f"Source: {config_dir}")
    console.print(f"Destination: {BACKUP_DIR}")
    console.print(
        "\n[yellow]Configuration files can contain private information, "
        "including application tokens and settings. "
        "This archive stays on your computer.[/yellow]"
    )

    if not typer.confirm("Create a configuration backup?", default=False):
        console.print("[dim]Backup cancelled.[/dim]")
        return

    try:
        BACKUP_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        destination = BACKUP_DIR / f"ghost-config-{timestamp}.tar.gz"

        with tarfile.open(destination, "w:gz") as archive:
            archive.add(config_dir, arcname=".config", recursive=True)

        destination.chmod(0o600)

        console.print("\n[green]Backup created successfully.[/green]")
        console.print(f"Location: {destination}")
        console.print(f"Size: {format_size(destination.stat().st_size)}")

    except (OSError, tarfile.TarError) as error:
        console.print(f"[red]Backup failed: {error}[/red]")

        if "destination" in locals():
            try:
                destination.unlink(missing_ok=True)
            except OSError:
                pass


def run_command(command: list[str]) -> tuple[str, int | None]:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return result.stdout.strip(), result.returncode
    except (OSError, subprocess.TimeoutExpired):
        return "", None


def security_report(console: Console) -> None:
    console.print("\n[bold white]◈ ghost. / security[/bold white]")
    console.print("[dim]Basic security checks · Read-only[/dim]\n")

    table = Table()
    table.add_column("Check")
    table.add_column("Result")
    table.add_column("Status")

    # Firewall checks
    firewall_active = False
    firewall_available = False

    for service in ("firewalld", "ufw"):
        output, code = run_command(["systemctl", "is-active", service])

        if code is not None:
            firewall_available = True

        if output == "active":
            firewall_active = True

    if firewall_active:
        table.add_row("Firewall service", "Active", "[green]OK[/green]")
    elif firewall_available:
        table.add_row(
            "Firewall service",
            "No checked firewall service is active",
            "[yellow]CHECK[/yellow]",
        )
    else:
        table.add_row(
            "Firewall service",
            "Could not inspect systemd",
            "[dim]UNKNOWN[/dim]",
        )

    # Secure Boot
    output, code = run_command(["mokutil", "--sb-state"])

    if code == 0:
        if "enabled" in output.lower():
            table.add_row("Secure Boot", output, "[green]ON[/green]")
        elif "disabled" in output.lower():
            table.add_row("Secure Boot", output, "[yellow]OFF[/yellow]")
        else:
            table.add_row("Secure Boot", output, "[dim]INFO[/dim]")
    else:
        table.add_row(
            "Secure Boot",
            "Could not determine status (mokutil may be missing)",
            "[dim]UNKNOWN[/dim]",
        )

    # SSH server
    output, code = run_command(["systemctl", "is-enabled", "sshd"])

    if output == "enabled":
        table.add_row(
            "SSH server",
            "Enabled at startup",
            "[yellow]CHECK[/yellow]",
        )
    elif output in ("disabled", "masked", "static"):
        table.add_row(
            "SSH server",
            output.capitalize(),
            "[green]OK[/green]",
        )
    else:
        table.add_row(
            "SSH server",
            "Could not determine status",
            "[dim]UNKNOWN[/dim]",
        )

    # Root accounts
    try:
        root_accounts = []

        for line in Path("/etc/passwd").read_text().splitlines():
            parts = line.split(":")

            if len(parts) >= 4 and parts[2] == "0":
                root_accounts.append(parts[0])

        table.add_row(
            "UID 0 accounts",
            ", ".join(root_accounts) or "None detected",
            "[green]OK[/green]" if root_accounts == ["root"] else "[yellow]CHECK[/yellow]",
        )
    except OSError:
        table.add_row(
            "UID 0 accounts",
            "Could not read /etc/passwd",
            "[dim]UNKNOWN[/dim]",
        )

    # Package updates
    output, code = run_command(["pacman", "-Qu"])

    if code in (0, 1):
        count = len(output.splitlines()) if output else 0
        table.add_row(
            "Package updates",
            f"{count} available",
            "[yellow]CHECK[/yellow]" if count else "[green]OK[/green]",
        )
    else:
        table.add_row(
            "Package updates",
            "Could not check",
            "[dim]UNKNOWN[/dim]",
        )

    console.print(table)

    console.print(
        "\n[dim]These are basic indicators, not a complete security audit. "
        "No settings were changed.[/dim]"
    )
