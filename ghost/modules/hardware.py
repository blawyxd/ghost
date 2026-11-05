
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path

from rich.console import Console
from rich.table import Table


def run_command(command: list[str], timeout: int = 10) -> str | None:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass

    return None


def read_file(path: str) -> str:
    try:
        return Path(path).read_text(errors="replace").strip()
    except OSError:
        return ""


def get_cpu_info() -> dict[str, str]:
    cpuinfo = read_file("/proc/cpuinfo")

    model = "Unknown"
    physical_cores: set[tuple[str, str]] = set()

    for line in cpuinfo.splitlines():
        if line.startswith("model name"):
            model = line.split(":", 1)[1].strip()
            break

    processor_id = "0"
    core_id = None

    for line in cpuinfo.splitlines() + [""]:
        if line.startswith("physical id"):
            processor_id = line.split(":", 1)[1].strip()
        elif line.startswith("core id"):
            core_id = line.split(":", 1)[1].strip()
        elif not line.strip():
            if core_id is not None:
                physical_cores.add((processor_id, core_id))
            processor_id = "0"
            core_id = None

    threads = os.cpu_count() or 0
    cores = len(physical_cores)

    frequency = read_file(
        "/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq"
    )

    if frequency.isdigit():
        frequency = f"{int(frequency) / 1000:.0f} MHz"
    else:
        frequency = "Unavailable"

    return {
        "model": model,
        "cores": str(cores) if cores else "Unknown",
        "threads": str(threads),
        "frequency": frequency,
    }


def get_memory_info() -> dict[str, str]:
    values = {}

    for line in read_file("/proc/meminfo").splitlines():
        parts = line.split()

        if len(parts) >= 2:
            try:
                values[parts[0].rstrip(":")] = int(parts[1])
            except ValueError:
                continue

    total = values.get("MemTotal")
    available = values.get("MemAvailable")

    if total is None or available is None or total <= 0 or not 0 <= available <= total:
        return {"total": "Unknown", "used": "Unknown", "available": "Unknown"}
    used = total - available

    return {
        "total": f"{total / 1024 / 1024:.2f} GB",
        "used": f"{used / 1024 / 1024:.2f} GB",
        "available": f"{available / 1024 / 1024:.2f} GB",
    }


def get_gpu_info() -> list[tuple[str, str]] | None:
    devices = []

    nvidia = run_command([
        "nvidia-smi",
        "--query-gpu=name,driver_version,memory.total",
        "--format=csv,noheader",
    ])

    if nvidia:
        for line in nvidia.splitlines():
            parts = [part.strip() for part in line.split(",")]

            if len(parts) >= 3:
                devices.append((
                    parts[0],
                    f"Driver {parts[1]} · {parts[2]} VRAM",
                ))

    pci_result = run_command(["lspci"])
    if nvidia is None and pci_result is None:
        return None
    pci = pci_result or ""

    for line in pci.splitlines():
        if re.search(r"VGA compatible controller|3D controller|Display controller", line, re.I):
            description = line.split(": ", 1)[-1].strip()

            if not any(name in description for name, _ in devices):
                devices.append((description, "PCI device"))

    return devices


def get_motherboard_info() -> dict[str, str]:
    return {
        "manufacturer": read_file("/sys/class/dmi/id/board_vendor") or "Unknown",
        "model": read_file("/sys/class/dmi/id/board_name") or "Unknown",
        "bios": read_file("/sys/class/dmi/id/bios_version") or "Unknown",
    }


def get_storage_info() -> list[dict[str, str]] | None:
    """Return detected physical drives, or None when lsblk data is unavailable."""
    output = run_command([
        "lsblk",
        "--json",
        "-o",
        "NAME,MODEL,SIZE,TYPE,TRAN,MOUNTPOINTS",
    ])

    if output is None:
        return None

    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("blockdevices"), list):
        return None

    drives = []

    def walk(devices: list[dict]) -> None:
        for device in devices:
            if device.get("type") == "disk":
                name = device.get("name") or "Unknown"
                if name.startswith(("zram", "loop")):
                    walk(device.get("children") or [])
                    continue
                drives.append({
                    "name": name,
                    "model": (device.get("model") or "").strip() or "Unknown",
                    "size": device.get("size") or "Unknown",
                    "transport": device.get("tran") or "Unknown",
                })

            walk(device.get("children") or [])

    walk(data.get("blockdevices") or [])
    return drives


def get_temperature_info() -> list[tuple[str, str]]:
    """Read available Linux thermal and hwmon temperature sensors."""
    readings: list[tuple[str, str]] = []
    sensor_paths = list(Path("/sys/class/thermal").glob("thermal_zone*/temp"))
    for path in sensor_paths:
        try:
            value = int(path.read_text().strip())
        except (OSError, ValueError):
            continue
        zone = path.parent
        label = ""
        try:
            label = (zone / "type").read_text().strip()
        except OSError:
            pass
        readings.append((label or zone.name, f"{value / 1000:.1f} °C"))

    for path in Path("/sys/class/hwmon").glob("hwmon*/temp*_input"):
        try:
            value = int(path.read_text().strip())
        except (OSError, ValueError):
            continue
        stem = path.name.removesuffix("_input")
        try:
            label = (path.parent / f"{stem}_label").read_text().strip()
        except OSError:
            label = stem
        try:
            chip = (path.parent / "name").read_text().strip()
        except OSError:
            chip = path.parent.name
        readings.append((f"{chip} {label}".strip(), f"{value / 1000:.1f} °C"))

    # hwmon and thermal zones can expose the same sensor; retain stable unique rows.
    return list(dict.fromkeys(readings))


def get_disk_health(drives: list[dict[str, str]]) -> list[tuple[str, str, str]]:
    """Return read-only SMART health results; unknown is explicit on tool errors."""
    if not shutil.which("smartctl"):
        return [(drive["name"], "UNAVAILABLE", "smartctl is not installed") for drive in drives]

    results = []
    for drive in drives:
        device = f"/dev/{drive['name']}"
        try:
            result = subprocess.run(
                ["smartctl", "--health", device], capture_output=True,
                text=True, timeout=8, check=False,
            )
        except subprocess.TimeoutExpired:
            results.append((drive["name"], "UNKNOWN", "smartctl timed out"))
            continue
        except OSError as error:
            results.append((drive["name"], "UNKNOWN", str(error)))
            continue

        output = (result.stdout + "\n" + result.stderr).strip()
        match = re.search(r"SMART overall-health self-assessment test result:\s*(\w+)", output, re.I)
        if match:
            status = match.group(1).upper()
            results.append((drive["name"], status, "SMART health self-assessment"))
        elif "SMART support is: Disabled" in output:
            results.append((drive["name"], "UNAVAILABLE", "SMART support is disabled"))
        else:
            detail = output.splitlines()[-1] if output else f"smartctl exited {result.returncode}"
            results.append((drive["name"], "UNKNOWN", detail))
    return results


def hardware_report(console: Console) -> None:
    console.print("\n[bold white]◈ ghost. / hardware[/bold white]")
    console.print("[dim]Hardware overview · Read-only[/dim]\n")

    cpu = get_cpu_info()
    memory = get_memory_info()
    motherboard = get_motherboard_info()

    system = Table(title="System", header_style="bold white")
    system.add_column("Component")
    system.add_column("Information")

    system.add_row("Distribution", read_file("/etc/os-release").split('PRETTY_NAME="')[-1].split('"')[0] if 'PRETTY_NAME="' in read_file("/etc/os-release") else "Unknown")
    system.add_row("Kernel", platform.release())
    system.add_row("Architecture", platform.machine())

    console.print(system)

    cpu_table = Table(title="Processor", header_style="bold white")
    cpu_table.add_column("Property")
    cpu_table.add_column("Value")

    cpu_table.add_row("Model", cpu["model"])
    cpu_table.add_row("Physical cores", cpu["cores"])
    cpu_table.add_row("Logical threads", cpu["threads"])
    cpu_table.add_row("Current frequency", cpu["frequency"])

    console.print(cpu_table)

    memory_table = Table(title="Memory", header_style="bold white")
    memory_table.add_column("Property")
    memory_table.add_column("Value")

    for name, value in memory.items():
        memory_table.add_row(name.capitalize(), value)

    console.print(memory_table)

    gpu_table = Table(title="Graphics", header_style="bold white")
    gpu_table.add_column("GPU")
    gpu_table.add_column("Details")

    gpus = get_gpu_info()

    if gpus:
        for name, details in gpus:
            gpu_table.add_row(name, details)
    elif gpus is None:
        gpu_table.add_row("Unknown", "Could not inspect graphics hardware; lspci and nvidia-smi unavailable or failed")
    else:
        gpu_table.add_row("None detected", "No graphics device reported by available tools")

    console.print(gpu_table)

    temperature_table = Table(title="Temperatures", header_style="bold white")
    temperature_table.add_column("Sensor")
    temperature_table.add_column("Reading", justify="right")
    temperature_table.add_column("Assessment")
    temperatures = get_temperature_info()
    high_temperature = False
    if temperatures:
        for name, reading in temperatures:
            try:
                high = float(reading.split()[0]) >= 90
            except ValueError:
                high = False
            high_temperature = high_temperature or high
            assessment = "[yellow]HIGH · verify sensor[/yellow]" if high else "[dim]INFO[/dim]"
            temperature_table.add_row(name, reading, assessment)
    else:
        temperature_table.add_row("Sensors", "Unavailable or not exposed by the kernel", "[dim]UNKNOWN[/dim]")
    console.print(temperature_table)
    if high_temperature:
        console.print(
            "[yellow]At least one sensor reports 90 °C or higher. Sensor limits vary; "
            "identify the component and compare with its manufacturer guidance.[/yellow]"
        )

    board_table = Table(title="Motherboard", header_style="bold white")
    board_table.add_column("Property")
    board_table.add_column("Value")

    board_table.add_row("Manufacturer", motherboard["manufacturer"])
    board_table.add_row("Model", motherboard["model"])
    board_table.add_row("BIOS", motherboard["bios"])

    console.print(board_table)

    storage_table = Table(title="Storage drives", header_style="bold white")
    storage_table.add_column("Device")
    storage_table.add_column("Model")
    storage_table.add_column("Size")
    storage_table.add_column("Connection")

    drives = get_storage_info()

    if drives:
        for drive in drives:
            storage_table.add_row(
                drive["name"],
                drive["model"],
                drive["size"],
                drive["transport"],
            )
    elif drives is None:
        storage_table.add_row("Unknown", "Could not inspect storage; lsblk unavailable or failed", "-", "-")
    else:
        storage_table.add_row("Unknown", "Could not detect drives", "-", "-")

    console.print(storage_table)

    health_table = Table(title="Disk health · SMART", header_style="bold white")
    health_table.add_column("Device")
    health_table.add_column("Status")
    health_table.add_column("Details")
    health_results = get_disk_health(drives or [])
    if health_results:
        for device, status, details in health_results:
            style = "green" if status == "PASSED" else "yellow" if status in {"FAILED", "UNKNOWN"} else "dim"
            health_table.add_row(device, f"[{style}]{status}[/{style}]", details)
    elif drives is None:
        health_table.add_row("Unknown", "UNKNOWN", "Storage inventory unavailable; health not checked")
    else:
        health_table.add_row("No drives", "INFO", "No physical drives detected")
    console.print(health_table)
    console.print("\n[dim]No hardware settings were changed.[/dim]")
