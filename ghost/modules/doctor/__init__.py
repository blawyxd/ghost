
from __future__ import annotations

import platform
import shutil
import subprocess
from pathlib import Path

from rich.console import Console
from rich.table import Table


def run_command(command: list[str]) -> str | None:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass

    return None


def parse_memory_usage(meminfo_text: str) -> tuple[int, int, float] | None:
    """Return used KiB, total KiB, and used percent when both inputs exist."""
    values: dict[str, int] = {}
    for line in meminfo_text.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            try:
                values[parts[0].rstrip(":")] = int(parts[1])
            except ValueError:
                continue
    total = values.get("MemTotal")
    available = values.get("MemAvailable")
    if total is None or available is None or total <= 0 or not 0 <= available <= total:
        return None
    used = total - available
    return used, total, used / total * 100


def doctor_report(console: Console) -> None:
    console.print("\n[bold white]◈ ghost. / doctor[/bold white]")
    console.print("[dim]Read-only system diagnostics[/dim]\n")

    table = Table(show_header=True, header_style="bold white")
    table.add_column("Check")
    table.add_column("Result")
    table.add_column("Status", justify="right")

    warnings = 0
    unknowns = 0

    os_release = Path("/etc/os-release")
    distro = "Unknown"

    if os_release.exists():
        try:
            for line in os_release.read_text(errors="replace").splitlines():
                if line.startswith("PRETTY_NAME="):
                    distro = line.split("=", 1)[1].strip().strip('"')
                    break
        except OSError:
            pass

    if distro == "Unknown":
        unknowns += 1
        table.add_row("Distribution", distro, "[cyan]INFO[/cyan]")
    else:
        table.add_row("Distribution", distro, "[green]OK[/green]")
    table.add_row("Kernel", platform.release(), "[green]OK[/green]")
    table.add_row("Architecture", platform.machine(), "[green]OK[/green]")

    cpu = "Unknown"
    cpuinfo = Path("/proc/cpuinfo")

    if cpuinfo.exists():
        try:
            for line in cpuinfo.read_text(errors="replace").splitlines():
                if line.startswith("model name"):
                    cpu = line.split(":", 1)[1].strip()
                    break
        except OSError:
            pass

    if cpu == "Unknown":
        unknowns += 1
        table.add_row("CPU", cpu, "[cyan]INFO[/cyan]")
    else:
        table.add_row("CPU", cpu, "[green]OK[/green]")

    meminfo = Path("/proc/meminfo")

    memory_usage = None
    if meminfo.exists():
        try:
            memory_text = meminfo.read_text(errors="replace")
        except OSError:
            memory_text = ""
        memory_usage = parse_memory_usage(memory_text)

    if memory_usage is not None:
        used, total, percent = memory_usage
        status = "WARN" if percent >= 90 else "OK"
        colour = "yellow" if percent >= 90 else "green"
        if percent >= 90:
            warnings += 1
        table.add_row(
            "Memory",
            f"{used / 1024:.0f} / {total / 1024:.0f} MB ({percent:.1f}% used)",
            f"[{colour}]{status}[/{colour}]",
        )
    else:
        unknowns += 1
        table.add_row("Memory", "Could not read memory totals", "[cyan]INFO[/cyan]")

    try:
        disk = shutil.disk_usage("/")
        percent = disk.used / disk.total * 100
        status = "WARN" if percent >= 90 else "OK"
        colour = "yellow" if percent >= 90 else "green"

        if percent >= 90:
            warnings += 1

        table.add_row(
            "Root storage",
            f"{disk.free / 1024**3:.1f} GB free ({percent:.1f}% used)",
            f"[{colour}]{status}[/{colour}]",
        )
    except OSError:
        unknowns += 1
        table.add_row("Root storage", "Could not inspect", "[cyan]INFO[/cyan]")

    gpu_result = run_command(["lspci"])
    gpu_output = gpu_result or ""

    graphics = [
        line.strip()
        for line in gpu_output.splitlines()
        if any(
            marker in line.lower()
            for marker in (
                "vga compatible controller",
                "3d controller",
                "display controller",
            )
        )
    ]

    if gpu_result is None:
        unknowns += 1
        table.add_row("GPU", "Could not inspect; lspci unavailable", "[cyan]INFO[/cyan]")
    elif graphics:
        table.add_row("GPU", "; ".join(graphics), "[cyan]INFO[/cyan]")
    else:
        table.add_row("GPU", "No graphics device detected by lspci", "[cyan]INFO[/cyan]")

    network = run_command(["ip", "route", "show", "default"])

    if network:
        table.add_row("Network", "Default route detected", "[green]OK[/green]")
    elif network is None:
        unknowns += 1
        table.add_row("Network", "Could not inspect routes; ip unavailable or failed", "[cyan]INFO[/cyan]")
    else:
        warnings += 1
        table.add_row("Network", "No default route detected", "[yellow]WARN[/yellow]")

    failed = run_command([
        "systemctl",
        "--failed",
        "--no-legend",
        "--plain",
    ])

    failed_services = [line for line in (failed or "").splitlines() if line.strip()]

    if failed is None:
        unknowns += 1
        table.add_row("Failed services", "Could not inspect systemd", "[cyan]INFO[/cyan]")
    elif failed_services:
        warnings += 1
        table.add_row(
            "Failed services",
            f"{len(failed_services)} failed",
            "[yellow]WARN[/yellow]",
        )
    else:
        table.add_row(
            "Failed services",
            "No failed services",
            "[green]OK[/green]",
        )

    if shutil.which("pacman"):
        updates = run_command(["pacman", "-Qu"])

        if updates is not None:
            count = len([
                line for line in updates.splitlines()
                if line.strip()
            ])

            table.add_row(
                "Package updates",
                f"{count} available",
                "[cyan]INFO[/cyan]" if count else "[green]OK[/green]",
            )
        else:
            unknowns += 1
            table.add_row("Package updates", "pacman check failed", "[cyan]INFO[/cyan]")

    console.print(table)
    console.print()

    if warnings:
        console.print(f"[yellow]{warnings} warning(s) detected.[/yellow]")
    elif unknowns:
        console.print(
            f"[cyan]No warning was detected by available checks; {unknowns} check(s) were unknown or unavailable.[/cyan]"
        )
    else:
        console.print("[green]No obvious system problems detected.[/green]")

    console.print("\n[dim]Ghost inspected your system. Nothing was changed.[/dim]")
