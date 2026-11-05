
from __future__ import annotations

import os
import shutil
import subprocess
import tarfile
import zlib
from datetime import datetime
from pathlib import Path
from pathlib import PurePosixPath

import typer
from rich.console import Console
from rich.table import Table


CACHE_DIR = Path.home() / ".cache"
BACKUP_DIR = Path.home() / "GhostBackups"
TEMP_DIRS = (Path("/tmp"), Path("/var/tmp"))


def format_size(size: int) -> str:
    value = float(size)

    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024

    return f"{value:.1f} TB"


def cache_usage() -> tuple[int, int]:
    inventory = _cache_inventory()
    return (inventory[0], inventory[1]) if inventory is not None else (0, 0)


def _cache_inventory() -> tuple[int, int, list[tuple[Path, str, int]]] | None:
    """Measure cache contents and direct removal targets in one traversal."""
    if not CACHE_DIR.is_dir() or CACHE_DIR.is_symlink():
        return None
    try:
        children = sorted(CACHE_DIR.iterdir(), key=lambda path: path.name.casefold())
    except OSError:
        return None
    kinds: dict[str, str] = {}
    sizes: dict[str, int] = {}
    for child in children:
        if child.is_symlink():
            kinds[child.name] = "Symbolic link"
        elif child.is_dir():
            kinds[child.name] = "Directory (recursive)"
        elif child.is_file():
            kinds[child.name] = "File"
        else:
            kinds[child.name] = "Other entry"
        sizes[child.name] = 0
    total_size = 0
    file_count = 0
    walk_errors: list[OSError] = []
    for root, dirs, filenames in os.walk(CACHE_DIR, followlinks=False, onerror=walk_errors.append):
        dirs[:] = [name for name in dirs if not (Path(root) / name).is_symlink()]
        for name in filenames:
            path = Path(root) / name
            if path.is_symlink():
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            total_size += size
            file_count += 1
            relative = path.relative_to(CACHE_DIR)
            sizes[relative.parts[0]] = sizes.get(relative.parts[0], 0) + size
    if walk_errors:
        return None
    entries = [(child, kinds[child.name], sizes[child.name]) for child in children]
    return total_size, file_count, entries


def _tree_size(path: Path) -> int:
    """Estimate an entry's size without following symbolic links."""
    if path.is_symlink():
        return 0
    try:
        if path.is_file():
            return path.stat().st_size
    except OSError:
        return 0
    total = 0
    if path.is_dir():
        for root, dirs, files in os.walk(path, followlinks=False):
            dirs[:] = [name for name in dirs if not (Path(root) / name).is_symlink()]
            for name in files:
                item = Path(root) / name
                if item.is_symlink():
                    continue
                try:
                    total += item.stat().st_size
                except OSError:
                    continue
    return total


def _cache_children() -> list[tuple[Path, str, int]]:
    inventory = _cache_inventory()
    return inventory[2] if inventory is not None else []


def cache_report(console: Console) -> None:
    console.print("\n[bold white]◈ ghost. / cache[/bold white]")
    console.print("[dim]Cache storage overview[/dim]\n")

    if not CACHE_DIR.is_dir() or CACHE_DIR.is_symlink():
        console.print("[yellow]No cache directory found.[/yellow]")
        return

    inventory = _cache_inventory()
    if inventory is None:
        console.print("[yellow]Could not read the cache directory; size is unknown.[/yellow]")
        return
    size, files, _ = inventory

    table = Table(show_header=False, box=None)
    table.add_row("Location", str(CACHE_DIR))
    table.add_row("Total size", f"[bold cyan]{format_size(size)}[/bold cyan]")
    table.add_row("Files", f"{files:,}")

    console.print(table)


def clean_cache(console: Console) -> None:
    console.print("\n[bold white]◈ ghost. / clean[/bold white]")
    console.print("[dim]Cache cleanup[/dim]\n")

    if not CACHE_DIR.is_dir() or CACHE_DIR.is_symlink():
        console.print("[yellow]No cache directory found.[/yellow]")
        return

    inventory = _cache_inventory()
    if inventory is None:
        console.print("[red]Could not fully inspect the cache directory; cleanup was not started.[/red]")
        return
    size, files, children = inventory

    console.print(f"Cache location: [cyan]{CACHE_DIR}[/cyan]")
    console.print(f"Files detected: [cyan]{files:,}[/cyan]")
    console.print(f"Space used: [cyan]{format_size(size)}[/cyan]")
    console.print("\n[bold]Removal targets[/bold]")
    preview = Table()
    preview.add_column("Entry")
    preview.add_column("Type")
    preview.add_column("Estimated size", justify="right")
    for child, kind, child_size in children:
        preview.add_row(str(child), kind, format_size(child_size))
    console.print(preview)
    console.print(f"Estimated space recovered: [bold]{format_size(size)}[/bold]")

    console.print(
        "\n[yellow]This removes the contents of ~/.cache. "
        "Some applications may need to rebuild their caches.[/yellow]"
    )

    if not typer.confirm("Continue with cleanup?", default=False):
        console.print("[dim]Cleanup cancelled.[/dim]")
        return

    removed = 0
    errors = 0

    for child, _, _ in children:
        try:
            if child.is_symlink() or child.is_file():
                child.unlink()
            elif child.is_dir():
                shutil.rmtree(child)
            else:
                continue

            removed += 1

        except OSError:
            errors += 1

    console.print(f"\n[green]Removed {removed} cache entries.[/green]")

    if errors:
        console.print(f"[yellow]Could not remove {errors} entries.[/yellow]")

    remaining = _cache_inventory()
    if remaining is None:
        console.print("Remaining cache size: [yellow]Unknown; could not recheck the directory.[/yellow]")
    else:
        console.print(f"Remaining cache size: [cyan]{format_size(remaining[0])}[/cyan]")


def create_backup(console: Console) -> None:
    console.print("\n[bold white]◈ ghost. / backup[/bold white]")
    console.print("[dim]Configuration backup[/dim]\n")

    config_dir = Path.home() / ".config"

    if not config_dir.is_dir() or config_dir.is_symlink():
        console.print("[yellow]No ~/.config directory found.[/yellow]")
        return

    console.print(f"Source: [cyan]{config_dir}[/cyan]")
    console.print(f"Destination: [cyan]{BACKUP_DIR}[/cyan]")

    console.print(
        "\n[yellow]Configuration backups may contain private information, "
        "including application tokens and settings.[/yellow]"
    )

    if not typer.confirm("Create a backup?", default=False):
        console.print("[dim]Backup cancelled.[/dim]")
        return

    try:
        if BACKUP_DIR.is_symlink():
            console.print("[red]Backup destination is a symbolic link; refusing to write.[/red]")
            return
        BACKUP_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        archive_path = BACKUP_DIR / f"ghost-config-{timestamp}.tar.gz"

        with tarfile.open(archive_path, "w:gz") as archive:
            archive.add(config_dir, arcname=".config")

        archive_path.chmod(0o600)

        console.print("\n[green]Backup created successfully.[/green]")
        console.print(f"File: [cyan]{archive_path}[/cyan]")
        console.print(
            f"Size: [cyan]{format_size(archive_path.stat().st_size)}[/cyan]"
        )

    except (OSError, tarfile.TarError) as error:
        console.print(f"\n[red]Backup failed: {error}[/red]")


def backups_report(console: Console) -> None:
    """List local configuration archives and check that each can be read."""
    console.print("\n[bold white]◈ ghost. / backups[/bold white]")
    console.print("[dim]Local backup inventory · Read-only[/dim]\n")
    if not BACKUP_DIR.is_dir() or BACKUP_DIR.is_symlink():
        console.print("[yellow]Backup directory not found.[/yellow]")
        return
    archives = sorted(BACKUP_DIR.glob("ghost-config-*.tar.gz"), key=lambda path: path.name)
    if not archives:
        console.print("[dim]No Ghost configuration backups found.[/dim]")
        return
    table = Table()
    table.add_column("Archive")
    table.add_column("Created")
    table.add_column("Size", justify="right")
    table.add_column("Readable")
    for archive in archives:
        if archive.is_symlink() or not archive.is_file():
            table.add_row(archive.name, "Unknown", "Unknown", "[yellow]No[/yellow]")
            continue
        try:
            stat = archive.stat()
            with tarfile.open(archive, "r:gz") as stream:
                members = stream.getmembers()
                readable = "Yes" if _verify_archive_payloads(stream, members) else "No"
                if not members:
                    readable = "Empty"
            table.add_row(
                archive.name,
                datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="minutes"),
                format_size(stat.st_size),
                readable,
            )
        except (OSError, tarfile.TarError, EOFError, zlib.error):
            table.add_row(archive.name, "Unknown", "Unknown", "[yellow]No[/yellow]")
    console.print(table)


def _verify_archive_payloads(
    archive: tarfile.TarFile,
    members: list[tarfile.TarInfo],
) -> bool:
    """Read members and drain the stream so truncated/corrupt compression fails validation."""
    for member in members:
        if not member.isfile():
            continue
        try:
            source = archive.extractfile(member)
            if source is None:
                return False
            remaining = member.size
            with source:
                while remaining:
                    chunk = source.read(min(1024 * 1024, remaining))
                    if not chunk:
                        return False
                    remaining -= len(chunk)
                if source.read(1):
                    return False
        except (OSError, tarfile.TarError, EOFError, zlib.error):
            return False
    # tarfile stops at the tar end markers, before gzip has checked its trailer
    # (including the CRC). Consume the compressed stream fully to validate it.
    try:
        while archive.fileobj.read(1024 * 1024):
            pass
    except (OSError, tarfile.TarError, EOFError, zlib.error):
        return False
    return True


def _safe_restore_target(config_dir: Path, archive_name: str) -> Path | None:
    """Map a tar member below .config while rejecting traversal and symlinks."""
    member_path = PurePosixPath(archive_name)
    if member_path.is_absolute() or ".." in member_path.parts or len(member_path.parts) < 2:
        return None
    if member_path.parts[0] != ".config" or any(part in {"", "."} for part in member_path.parts):
        return None
    relative = Path(*member_path.parts[1:])
    if relative.is_absolute() or ".." in relative.parts:
        return None
    target = config_dir / relative
    try:
        target.relative_to(config_dir)
    except ValueError:
        return None
    if config_dir.is_symlink():
        return None
    current = config_dir
    for part in relative.parts[:-1]:
        current = current / part
        if current.is_symlink() or (current.exists() and not current.is_dir()):
            return None
    if target.is_symlink():
        return None
    return target


def restore_backup(console: Console, archive_name: str) -> None:
    """Restore missing configuration files from a Ghost archive, without overwrites."""
    console.print("\n[bold white]◈ ghost. / restore backup[/bold white]")
    if (
        Path(archive_name).name != archive_name
        or not archive_name.startswith("ghost-config-")
        or not archive_name.endswith(".tar.gz")
        or not BACKUP_DIR.is_dir()
        or BACKUP_DIR.is_symlink()
    ):
        console.print("[red]Choose a listed Ghost backup archive by filename.[/red]")
        return
    archive_path = BACKUP_DIR / archive_name
    if archive_path.is_symlink() or not archive_path.is_file():
        console.print("[red]Backup archive is missing or is not a regular file.[/red]")
        return
    config_dir = Path.home() / ".config"
    if config_dir.is_symlink() or (config_dir.exists() and not config_dir.is_dir()):
        console.print("[red]~/.config is not a normal directory; refusing to restore.[/red]")
        return

    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            members = archive.getmembers()
            seen: set[Path] = set()
            plan: list[tuple[tarfile.TarInfo, Path]] = []
            conflicts: list[Path] = []
            rejected = 0
            total_bytes = 0
            for member in members:
                if not member.isfile():
                    if member.name.startswith(".config/") and not member.isdir():
                        rejected += 1
                    continue
                target = _safe_restore_target(config_dir, member.name)
                if target is None or target in seen:
                    rejected += 1
                    continue
                seen.add(target)
                if target.exists():
                    conflicts.append(target)
                    continue
                plan.append((member, target))
                total_bytes += member.size

            console.print(f"Archive: [cyan]{archive_name}[/cyan]")
            console.print(f"Destination: [cyan]{config_dir}[/cyan]")
            table = Table(title="Restore preview · Existing files will be kept")
            table.add_column("File")
            table.add_column("Action")
            table.add_column("Size", justify="right")
            for member, target in plan:
                table.add_row(str(target), "Restore", format_size(member.size))
            for target in conflicts:
                table.add_row(str(target), "Skip · already exists", "-")
            console.print(table)
            if rejected:
                console.print(f"[yellow]{rejected} unsafe, linked, duplicate, or unsupported archive entry/entries will be skipped.[/yellow]")
            console.print(f"Files to restore: {len(plan)} · Estimated data: {format_size(total_bytes)}")
            if not plan:
                console.print("[dim]No missing regular files are available to restore.[/dim]")
                return
            console.print("[yellow]Restored files are added only when the destination does not exist. No existing file will be overwritten.[/yellow]")
            if not typer.confirm("Restore these files?", default=False):
                console.print("[dim]Restore cancelled. Nothing was changed.[/dim]")
                return

            restored = 0
            errors = 0
            for member, target in plan:
                safe_target = _safe_restore_target(config_dir, member.name)
                if safe_target != target or target.exists():
                    errors += 1
                    continue
                try:
                    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                    if any(parent.is_symlink() for parent in (target.parent, *target.parent.parents) if parent != config_dir.parent):
                        errors += 1
                        continue
                    source = archive.extractfile(member)
                    if source is None:
                        errors += 1
                        continue
                    with source, target.open("xb") as destination:
                        shutil.copyfileobj(source, destination)
                    target.chmod(member.mode & 0o700)
                    restored += 1
                except (OSError, tarfile.TarError):
                    errors += 1
                    try:
                        target.unlink(missing_ok=True)
                    except OSError:
                        pass
            console.print(f"[green]Restored {restored} file(s).[/green]")
            if errors:
                console.print(f"[yellow]{errors} file(s) could not be restored.[/yellow]")
    except (OSError, tarfile.TarError) as error:
        console.print(f"[red]Could not read backup archive: {error}[/red]")


def temp_report(console: Console) -> None:
    """Inspect temporary-directory entries without deleting anything."""
    console.print("\n[bold white]◈ ghost. / temporary files[/bold white]")
    console.print("[dim]Temporary storage inventory · Read-only[/dim]\n")
    table = Table()
    table.add_column("Location")
    table.add_column("Entry")
    table.add_column("Type")
    table.add_column("Size", justify="right")
    found = 0
    unavailable = 0
    for directory in TEMP_DIRS:
        if not directory.is_dir() or directory.is_symlink():
            console.print(f"[dim]{directory}: unavailable[/dim]")
            unavailable += 1
            continue
        try:
            children = sorted(directory.iterdir(), key=lambda path: path.name.casefold())
        except OSError as error:
            console.print(f"[yellow]Could not inspect {directory}: {error}[/yellow]")
            unavailable += 1
            continue
        for child in children:
            try:
                if child.lstat().st_uid != os.getuid():
                    continue
            except OSError:
                continue
            if found >= 100:
                continue
            kind = "Symbolic link" if child.is_symlink() else "Directory" if child.is_dir() else "File" if child.is_file() else "Other"
            table.add_row(str(directory), child.name, kind, format_size(_tree_size(child)))
            found += 1
    if found:
        console.print(table)
        if found == 100:
            console.print("[dim]Showing the first 100 entries owned by your account.[/dim]")
        if unavailable:
            console.print(f"[yellow]{unavailable} temporary location(s) could not be inspected.[/yellow]")
    else:
        if unavailable:
            console.print("[yellow]No entries were listed; one or more temporary locations could not be inspected.[/yellow]")
        else:
            console.print("[dim]No entries found in the inspected temporary directories.[/dim]")
    console.print("[dim]Ghost only inspected these paths. Nothing was removed.[/dim]")


def orphans_report(console: Console) -> None:
    """List unneeded pacman dependencies without removing them."""
    console.print("\n[bold white]◈ ghost. / orphan packages[/bold white]")
    console.print("[dim]Pacman orphan inspection · Read-only[/dim]\n")
    if not shutil.which("pacman"):
        console.print("[yellow]pacman is not installed; orphan inspection is unavailable.[/yellow]")
        return
    result = run_command(["pacman", "-Qtdq"])
    if result is None:
        console.print("[yellow]Could not run pacman orphan inspection.[/yellow]")
        return
    if result.returncode not in (0, 1):
        detail = result.stderr.strip() or f"pacman exited with status {result.returncode}"
        console.print(f"[yellow]Orphan inspection failed: {detail}[/yellow]")
        return
    packages = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not packages:
        console.print("[green]No orphaned packages detected.[/green]")
        return
    console.print(f"[yellow]{len(packages)} orphaned package(s) detected:[/yellow]")
    for package in packages:
        console.print(f"  • {package}")
    console.print("\n[dim]No packages were removed. Review dependencies before uninstalling.[/dim]")


def run_command(command: list[str]) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def service_active(service: str) -> bool:
    return service_state(service) is True


def service_state(service: str) -> bool | None:
    """Return True for active, False for inactive, and None when unknown."""
    result = run_command(["systemctl", "is-active", "--quiet", service])
    if result is None:
        return None
    if result.returncode == 0:
        return True
    if result.returncode == 3:
        return False
    return None


def security_report(console: Console) -> None:
    console.print("\n[bold white]◈ ghost. / security[/bold white]")
    console.print("[dim]Basic security checks — read only[/dim]\n")

    table = Table(show_header=True, header_style="bold white")
    table.add_column("Check")
    table.add_column("Result")
    table.add_column("Status")

    firewall_services = ("firewalld", "ufw", "nftables")

    firewall_states = {service: service_state(service) for service in firewall_services}
    active_firewalls = [service for service, active in firewall_states.items() if active is True]
    unknown_firewalls = [service for service, active in firewall_states.items() if active is None]

    if active_firewalls:
        table.add_row(
            "Firewall services",
            ", ".join(active_firewalls),
            "[green]ACTIVE[/green]",
        )
    elif not unknown_firewalls:
        table.add_row(
            "Firewall services",
            "No checked firewall service is active",
            "[yellow]CHECK[/yellow]",
        )
    elif len(unknown_firewalls) == len(firewall_services):
        table.add_row(
            "Firewall services",
            "Could not inspect systemd firewall units",
            "[cyan]UNKNOWN[/cyan]",
        )
    else:
        table.add_row(
            "Firewall services",
            "Some firewall units could not be inspected: " + ", ".join(unknown_firewalls),
            "[cyan]INFO[/cyan]",
        )

    secure_boot = run_command(["mokutil", "--sb-state"])

    if secure_boot and secure_boot.returncode == 0:
        result = secure_boot.stdout.strip()
    elif shutil.which("mokutil"):
        result = "Could not determine Secure Boot state"
    else:
        result = "mokutil is not installed"

    table.add_row("Secure Boot", result, "[cyan]INFO[/cyan]")

    ssh_state = service_state("sshd")
    if ssh_state is True:
        table.add_row(
            "SSH server",
            "SSH service is active",
            "[yellow]REVIEW[/yellow]",
        )
    elif ssh_state is False:
        table.add_row(
            "SSH server",
            "SSH service is not active",
            "[green]OK[/green]",
        )
    else:
        table.add_row(
            "SSH server",
            "Could not inspect the SSH service",
            "[cyan]UNKNOWN[/cyan]",
        )

    passwd_file = Path("/etc/passwd")
    root_accounts = []

    try:
        for line in passwd_file.read_text(errors="replace").splitlines():
            fields = line.split(":")
            if len(fields) > 2 and fields[2] == "0":
                root_accounts.append(fields[0])
    except OSError:
        root_accounts = []

    if not root_accounts:
        table.add_row(
            "Root accounts",
            "Could not inspect /etc/passwd",
            "[cyan]UNKNOWN[/cyan]",
        )
    elif root_accounts == ["root"]:
        table.add_row(
            "Root accounts",
            "Only the standard root account has UID 0",
            "[green]OK[/green]",
        )
    else:
        table.add_row(
            "Root accounts",
            ", ".join(root_accounts) if root_accounts else "Could not inspect",
            "[yellow]REVIEW[/yellow]",
        )

    updates = run_command(["pacman", "-Qu"])

    if updates and updates.returncode in (0, 1):
        count = len([
            line for line in updates.stdout.splitlines()
            if line.strip()
        ])

        table.add_row(
            "Package updates",
            f"{count} available",
            "[yellow]UPDATE[/yellow]" if count else "[green]OK[/green]",
        )
    else:
        table.add_row(
            "Package updates",
            "Could not check",
            "[cyan]INFO[/cyan]",
        )

    console.print(table)

    console.print(
        "\n[dim]These checks are indicators, not a complete security audit. "
        "Ghost has not changed any system settings.[/dim]"
    )
