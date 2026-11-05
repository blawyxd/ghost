
from __future__ import annotations

import shutil
import subprocess

from rich.console import Console
from rich.table import Table
from rich.text import Text


def run_command(command: list[str], timeout: int = 10) -> tuple[str, str]:
    """Run a system command and return stdout and stderr."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode != 0:
            error = result.stderr.strip() or f"Command exited with status {result.returncode}."
            return "", error
        return result.stdout.strip(), result.stderr.strip()
    except (OSError, subprocess.TimeoutExpired) as error:
        return "", str(error)


def processes_report(console: Console) -> None:
    console.print("\n[bold white]◈ ghost. / processes[/bold white]")
    console.print("[dim]Running processes · Highest CPU usage first[/dim]\n")

    output, error = run_command([
        "ps", "-eo", "pid,comm,%cpu,%mem",
        "--sort=-%cpu",
    ])

    if not output:
        console.print(f"[red]Could not inspect processes: {error}[/red]")
        return

    lines = output.splitlines()[1:21]

    table = Table()
    table.add_column("PID", justify="right")
    table.add_column("Process")
    table.add_column("CPU %", justify="right")
    table.add_column("RAM %", justify="right")

    for line in lines:
        parts = line.split(None, 3)
        if len(parts) == 4:
            table.add_row(*parts)

    console.print(table)
    console.print("\n[dim]Showing up to 20 processes. Nothing was stopped.[/dim]")


def services_report(console: Console) -> None:
    console.print("\n[bold white]◈ ghost. / services[/bold white]")
    console.print("[dim]Systemd service overview · Read-only[/dim]\n")

    failed, error = run_command([
        "systemctl", "--failed", "--no-legend", "--no-pager",
    ])

    if failed:
        table = Table(title="Failed services", header_style="bold white")
        table.add_column("Unit")
        table.add_column("Load")
        table.add_column("Active")
        table.add_column("Description")

        for line in failed.splitlines():
            parts = line.split(None, 4)
            if len(parts) >= 4:
                table.add_row(
                    parts[0],
                    parts[1],
                    parts[2],
                    parts[4] if len(parts) > 4 else "",
                )

        console.print(table)
    elif error:
        console.print(f"[yellow]Could not inspect failed services: {error}[/yellow]")
    else:
        console.print("[green]No failed systemd services.[/green]")

    running, error = run_command([
        "systemctl",
        "list-units",
        "--type=service",
        "--state=running",
        "--no-legend",
        "--no-pager",
    ])

    if running:
        table = Table(title="Running services", header_style="bold white")
        table.add_column("Service")
        table.add_column("Status")
        table.add_column("Description")

        for line in running.splitlines()[:20]:
            parts = line.split(None, 4)
            if len(parts) >= 4:
                table.add_row(
                    parts[0],
                    parts[2],
                    parts[4] if len(parts) > 4 else "",
                )

        console.print(table)
        console.print("[dim]Showing up to 20 running services.[/dim]")
    elif error:
        console.print(f"[yellow]Could not list running services: {error}[/yellow]")


def network_report(console: Console) -> None:
    console.print("\n[bold white]◈ ghost. / network[/bold white]")
    console.print("[dim]Network interfaces and connectivity[/dim]\n")

    interfaces, error = run_command(["ip", "-brief", "address"])

    if interfaces:
        table = Table(title="Network interfaces", header_style="bold white")
        table.add_column("Interface")
        table.add_column("State")
        table.add_column("Addresses")

        for line in interfaces.splitlines():
            parts = line.split(None, 2)
            if len(parts) >= 2:
                table.add_row(
                    parts[0],
                    parts[1],
                    parts[2] if len(parts) > 2 else "-",
                )

        console.print(table)
    else:
        console.print(f"[yellow]Could not inspect interfaces: {error}[/yellow]")

    routes, error = run_command(["ip", "route", "show", "default"])

    console.print("\n[bold]Default route[/bold]")
    console.print(Text(routes or error or "No default route detected"))

    console.print("\n[bold]Connectivity[/bold]")

    if not shutil.which("ping"):
        console.print("[yellow]ping is not installed; internet test skipped.[/yellow]")
        return

    internet, error = run_command(
        ["ping", "-c", "1", "-W", "2", "1.1.1.1"],
        timeout=5,
    )

    if internet:
        console.print("[green]Internet connection test passed.[/green]")
    else:
        if error:
            console.print(f"[yellow]Internet connection test unavailable or failed: {error}[/yellow]")
        else:
            console.print("[yellow]Could not reach 1.1.1.1.[/yellow]")

    dns, error = run_command(["getent", "hosts", "archlinux.org"])

    if dns:
        console.print("[green]DNS lookup passed.[/green]")
    else:
        console.print(f"[yellow]DNS lookup failed or unavailable: {error}[/yellow]" if error else "[yellow]DNS lookup failed or unavailable.[/yellow]")


def ports_report(console: Console) -> None:
    console.print("\n[bold white]◈ ghost. / ports[/bold white]")
    console.print("[dim]Listening network sockets · Read-only[/dim]\n")

    output, error = run_command(["ss", "-tuln"])

    if not output:
        console.print(f"[red]Could not inspect ports: {error}[/red]")
        return

    lines = output.splitlines()

    table = Table()
    table.add_column("Protocol")
    table.add_column("State")
    table.add_column("Local address")
    table.add_column("Peer address")

    for line in lines[1:]:
        parts = line.split()

        if len(parts) >= 5:
            table.add_row(
                parts[0],
                parts[1],
                parts[4],
                parts[5] if len(parts) > 5 else "-",
            )

    console.print(table)

    console.print(
        "\n[dim]This lists sockets, not necessarily publicly accessible ports. "
        "No firewall settings were changed.[/dim]"
    )


def logs_report(console: Console, lines: int = 30) -> None:
    console.print("\n[bold white]◈ ghost. / logs[/bold white]")
    console.print("[dim]Current boot diagnostics and recent system journal · Read-only[/dim]\n")

    warnings, warning_error = run_command([
        "journalctl", "-b", "-p", "warning..alert", "-n", str(lines),
        "--no-pager", "-o", "short-iso",
    ])
    console.print("[bold]Warnings and errors from this boot[/bold]")
    if warnings:
        warning_lines = warnings.splitlines()
        console.print(
            f"[yellow]{len(warning_lines)} warning-or-higher entr"
            f"{'y' if len(warning_lines) == 1 else 'ies'} in the displayed sample.[/yellow]"
        )
        console.print(Text(warnings))
        console.print("[dim]A warning is a lead to investigate, not proof of a fault.[/dim]")
    elif warning_error:
        console.print(f"[yellow]Could not inspect current-boot warnings: {warning_error}[/yellow]")
    else:
        console.print("[green]No warning-or-higher entries returned for this boot.[/green]")

    output, error = run_command([
        "journalctl",
        "-n", str(lines),
        "--no-pager",
        "-o", "short-iso",
    ])

    if not output:
        console.print("[yellow]Could not read the system journal.[/yellow]")
        if error:
            console.print(Text(error))
        console.print(
            "[dim]Some journal entries may require additional permissions.[/dim]"
        )
        return

    console.print(Text(output))
    console.print("\n[dim]Logs were only read, not modified.[/dim]")
