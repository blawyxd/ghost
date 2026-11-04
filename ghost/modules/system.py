from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def check_updates() -> list[str] | None:
    """Return pacman updates without installing anything."""
    try:
        completed = subprocess.run(
            ["pacman", "-Qu"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

    if completed.returncode not in (0, 1):
        return None
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def disk_summary() -> list[str]:
    lines: list[str] = []
    targets = [Path.home(), Path("/")]
    seen: set[str] = set()

    for target in targets:
        try:
            usage = shutil.disk_usage(target)
        except OSError:
            continue
        device_key = str(usage.total)
        if device_key in seen:
            continue
        seen.add(device_key)

        total = usage.total / (1024 ** 3)
        used = usage.used / (1024 ** 3)
        free = usage.free / (1024 ** 3)
        percent = (usage.used / usage.total * 100) if usage.total else 0
        lines.append(f"[bold]{target}[/bold]  {used:.1f} GB used / {total:.1f} GB total")
        lines.append(f"  {free:.1f} GB free  ·  {percent:.1f}% used")
    return lines or ["Could not read disk usage."]


def find_large_files(
    limit: int = 12,
    max_files: int = 12000,
    minimum_bytes: int = 500 * 1024 ** 2,
) -> list[tuple[float, str]]:
    """Find large files in the user's home, with a safety scan cap."""
    home = Path.home()
    found: list[tuple[int, str]] = []
    checked = 0

    for current, dirs, filenames in os.walk(home, topdown=True):
        dirs[:] = [
            name for name in dirs
            if name not in {".cache", ".local/share/Trash", ".git", "node_modules", ".venv"}
        ]
        for filename in filenames:
            checked += 1
            if checked > max_files:
                break
            path = Path(current) / filename
            try:
                size = path.stat().st_size
            except (OSError, PermissionError):
                continue
            if size >= minimum_bytes:
                found.append((size, str(path)))
        if checked > max_files:
            break

    found.sort(reverse=True)
    return [(size / (1024 ** 3), path) for size, path in found[:limit]]
