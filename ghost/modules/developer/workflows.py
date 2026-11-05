"""Project-oriented developer helpers with explicit, reviewable side effects."""

from __future__ import annotations

import os
import json
import ipaddress
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:  # tomllib ships with Python 3.11; Ghost also supports Python 3.10.
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10
    tomllib = None  # type: ignore[assignment]

import typer
from rich.console import Console
from rich.table import Table


PROJECT_MARKERS = (
    "pyproject.toml", "requirements.txt", "setup.py", "package.json",
    "Cargo.toml", "go.mod", "pom.xml", "CMakeLists.txt", ".git",
)
IGNORED_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build",
    ".aws", ".ssh", ".gnupg", ".config", ".local", ".cache", ".secrets",
    ".agents", ".codex",
}


def find_project_root(directory: Path | None = None) -> Path | None:
    current = (directory or Path.cwd()).expanduser().resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if any((candidate / marker).exists() for marker in PROJECT_MARKERS):
            return candidate
    return None


def project_kind(root: Path) -> list[str]:
    kinds = []
    if (root / "pyproject.toml").exists() or (root / "requirements.txt").exists() or (root / "setup.py").exists():
        kinds.append("Python")
    if (root / "package.json").exists():
        kinds.append("Node.js")
    if (root / "Cargo.toml").exists():
        kinds.append("Rust")
    if (root / "go.mod").exists():
        kinds.append("Go")
    if (root / "pom.xml").exists():
        kinds.append("Java/Maven")
    if (root / "CMakeLists.txt").exists():
        kinds.append("CMake")
    if not kinds:
        kinds.append("Git repository")
    return kinds


def project_report(console: Console, directory: Path | None = None) -> None:
    target = (directory or Path.cwd()).expanduser().resolve()
    root = find_project_root(target)
    console.print("\n[bold white]◈ ghost. / project[/bold white]")
    if root is None:
        console.print(f"[yellow]No known project found from {target} upward.[/yellow]")
        console.print("Looked for: " + ", ".join(PROJECT_MARKERS))
        return
    console.print(f"[bold]Root:[/bold] {root}")
    console.print(f"[bold]Detected:[/bold] {', '.join(project_kind(root))}")

    environment = next((root / name for name in (".venv", "venv", "env") if (root / name).is_dir()), None)
    current_env = Path(sys.prefix).resolve() if sys.prefix != sys.base_prefix else None
    if current_env is not None:
        try:
            current_env.relative_to(root.resolve())
        except ValueError:
            current_env = None
    if current_env:
        env_status = f"Active: {current_env}"
    elif environment:
        env_status = f"Found, not active: {environment}"
    else:
        env_status = "No project virtual environment detected"
    console.print(f"[bold]Python environment:[/bold] {env_status}")

    table = Table(title="Project structure · depth 2")
    table.add_column("Path")
    table.add_column("Type")
    entries = 0
    for current, dirs, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        depth = len(current_path.relative_to(root).parts)
        dirs[:] = sorted(
            name for name in dirs
            if name not in IGNORED_DIRS and not (current_path / name).is_symlink()
        ) if depth < 2 else []
        relative = current_path.relative_to(root)
        if relative != Path("."):
            table.add_row(str(relative) + "/", "directory")
            entries += 1
        for filename in sorted(files):
            file_path = current_path / filename
            if file_path.is_symlink():
                continue
            table.add_row(str(file_path.relative_to(root)), "file")
            entries += 1
            if entries >= 200:
                break
        if entries >= 200:
            break
    console.print(table)
    if entries >= 200:
        console.print("[dim]Structure listing capped at 200 entries.[/dim]")


def declared_python_dependencies(root: Path) -> list[str]:
    dependencies: dict[str, str] = {}

    def add_dependency(item: str) -> None:
        match = re.match(r"([A-Za-z0-9][A-Za-z0-9._-]*)", item)
        key = re.sub(r"[-_.]+", "-", match.group(1)).casefold() if match else item.casefold()
        previous = dependencies.get(key)
        if previous is None:
            dependencies[key] = item
        elif previous == item or previous in item:
            dependencies[key] = item
        elif item in previous:
            pass
        else:
            dependencies[key] = f"{key} (declared differently: {previous}; {item})"
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            if tomllib is None:
                raise ValueError("TOML parsing requires Python 3.11 or newer")
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            project = data.get("project", {})
            for item in project.get("dependencies", []):
                add_dependency(str(item))
            optional = project.get("optional-dependencies", {})
            for group, values in optional.items():
                for item in values:
                    add_dependency(f"{item} [{group}]")
        except (OSError, ValueError, AttributeError, TypeError):
            add_dependency("Could not parse pyproject.toml with this Python version")
    requirements = root / "requirements.txt"
    if requirements.is_file():
        try:
            for line in requirements.read_text(encoding="utf-8").splitlines():
                value = line.split("#", 1)[0].strip()
                if value and not value.startswith(("-r ", "--")):
                    add_dependency(value)
        except OSError:
            add_dependency("Could not read requirements.txt")
    return list(dependencies.values())


def project_python(root: Path) -> str:
    """Prefer the project's existing virtual environment when it has Python."""
    current = Path(sys.prefix).resolve()
    try:
        current.relative_to(root.resolve())
        if sys.prefix != sys.base_prefix:
            return sys.executable
    except ValueError:
        pass
    for environment in (".venv", "venv", "env"):
        python = root / environment / "bin" / "python"
        if python.is_file() and os.access(python, os.X_OK):
            return str(python)
    return sys.executable


def project_deps_report(console: Console, directory: Path | None = None) -> None:
    target = find_project_root(directory)
    console.print("\n[bold white]◈ ghost. / project dependencies[/bold white]")
    if target is None:
        console.print("[yellow]No project root detected.[/yellow]")
        return
    dependencies = declared_python_dependencies(target)
    console.print(f"[bold]Project:[/bold] {target}")
    if not dependencies:
        console.print("[dim]No Python dependencies declared in pyproject.toml or requirements.txt.[/dim]")
        return
    table = Table()
    table.add_column("Declared dependency")
    for dependency in dependencies:
        table.add_row(dependency)
    console.print(table)
    console.print("\n[dim]These are project declarations; installed versions are not inferred.[/dim]")


def _test_command(root: Path, python: str) -> list[str] | None:
    has_tests = (root / "tests").is_dir() or any(root.glob("test_*.py")) or any(root.glob("*_test.py"))
    if not has_tests:
        return None
    if _module_available("pytest", python):
        return [python, "-m", "pytest"]
    tests_dir = root / "tests"
    if tests_dir.is_dir():
        return [python, "-m", "unittest", "discover", "-s", "tests"]
    return [python, "-m", "unittest", "discover", "-s", "."]


def test_project(console: Console, directory: Path | None = None) -> None:
    root = find_project_root(directory)
    if root is None:
        console.print("[yellow]No project root detected.[/yellow]")
        return
    command = _test_command(root, project_python(root))
    if command is None:
        console.print(f"[yellow]No test files found in {root}.[/yellow]")
        return
    console.print(f"[bold]Running:[/bold] {' '.join(command)}")
    _run_project_command(console, root, command, "Tests")


def build_project(console: Console, directory: Path | None = None) -> None:
    root = find_project_root(directory)
    if root is None:
        console.print("[yellow]No project root detected.[/yellow]")
        return
    command: list[str] | None = None
    if (root / "pyproject.toml").exists() and "Python" in project_kind(root):
        if not (root / "pyproject.toml").is_file():
            console.print("[yellow]pyproject.toml is not a file.[/yellow]")
            return
        python = project_python(root)
        if not _module_available("build", python):
            console.print("[yellow]Python build helper is unavailable. Install the 'build' package in your environment first.[/yellow]")
            console.print("[dim]Ghost did not install it.[/dim]")
            return
        command = [python, "-m", "build"]
    elif (root / "package.json").is_file():
        command, message = node_build_command(root)
        if command is None:
            console.print(f"[yellow]{message}[/yellow]")
            return
        console.print(f"[bold]Running:[/bold] {' '.join(command)}")
        _run_project_command(console, root, command, "Build")
        return
    elif (root / "Cargo.toml").is_file():
        if shutil.which("cargo"):
            command = ["cargo", "build"]
        else:
            console.print("[yellow]cargo is not installed.[/yellow]")
            return
    if command is None:
        console.print("[yellow]No supported build configuration found (Python, npm, or Cargo).[/yellow]")
        return
    console.print(f"[bold]Running:[/bold] {' '.join(command)}")
    _run_project_command(console, root, command, "Build")


def node_build_command(root: Path) -> tuple[list[str] | None, str]:
    """Return the declared Node build command, or an accurate skip reason."""
    package_json = root / "package.json"
    try:
        package = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return None, f"Could not read package.json: {error}"
    if not isinstance(package, dict) or not isinstance(package.get("scripts", {}), dict):
        return None, "package.json scripts must be an object."
    if "build" not in package.get("scripts", {}):
        return None, "package.json has no 'build' script; no build command was run."
    if not shutil.which("npm"):
        return None, "npm is not installed."
    return ["npm", "run", "build"], "Node.js build script"


def server_command(
    root: Path, host: str = "127.0.0.1", port: int = 8000,
    script: str | None = None,
) -> tuple[list[str] | None, str]:
    """Choose a known local development server without executing it."""
    if not 1 <= port <= 65535:
        return None, "Port must be between 1 and 65535."
    try:
        ipaddress.IPv4Address(host)
    except ipaddress.AddressValueError:
        return None, "Host must be an IPv4 address such as 127.0.0.1 or 0.0.0.0."
    python = project_python(root)
    manage_py = root / "manage.py"
    if manage_py.is_file():
        return [python, str(manage_py), "runserver", f"{host}:{port}"], "Django development server"
    package_json = root / "package.json"
    if package_json.is_file():
        try:
            package = json.loads(package_json.read_text(encoding="utf-8"))
            scripts = package.get("scripts", {})
        except (OSError, json.JSONDecodeError, AttributeError):
            return None, "Could not read package.json scripts."
        if not isinstance(scripts, dict):
            return None, "package.json scripts must be an object."
        selected = script or ("dev" if "dev" in scripts else "start" if "start" in scripts else None)
        if selected is None:
            return None, "package.json has no 'dev' or 'start' script."
        if selected not in scripts:
            return None, f"package.json has no '{selected}' script."
        if not shutil.which("npm"):
            return None, "npm is not installed."
        return ["npm", "run", selected, "--", "--host", host, "--port", str(port)], f"npm script '{selected}'"
    if (root / "index.html").is_file() or (root / "public" / "index.html").is_file():
        return [python, "-m", "http.server", str(port), "--bind", host], "Python static file server"
    return None, "No supported server found. Add index.html, manage.py, or a package.json dev/start script."


def serve_project(
    console: Console,
    directory: Path | None = None,
    host: str = "127.0.0.1",
    port: int = 8000,
    script: str | None = None,
) -> None:
    root = find_project_root(directory)
    if root is None:
        console.print("[yellow]No project root detected.[/yellow]")
        return
    command, server_name = server_command(root, host, port, script)
    if command is None:
        console.print(f"[yellow]{server_name}[/yellow]")
        return
    console.print(f"[bold]{server_name}[/bold]")
    console.print(f"Project: {root}")
    console.print(f"Address: http://{host}:{port}/")
    console.print(f"Command: {' '.join(command)}")
    if server_name.startswith("npm script"):
        console.print("[yellow]This runs code defined by the project's package.json script.[/yellow]")
    console.print("[dim]Press Ctrl+C to stop the server.[/dim]\n")
    try:
        result = subprocess.run(command, cwd=root, check=False)
    except KeyboardInterrupt:
        console.print("\n[dim]Server stopped.[/dim]")
        return
    except OSError as error:
        console.print(f"[red]Could not start server: {error}[/red]")
        return
    if result.returncode:
        console.print(f"[yellow]Server exited with status {result.returncode}.[/yellow]")


def _module_available(name: str, python: str = sys.executable) -> bool:
    try:
        result = subprocess.run(
            [python, "-c", "import importlib.util, sys; sys.exit(importlib.util.find_spec(sys.argv[1]) is None)", name],
            capture_output=True, text=True, timeout=5, check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _run_project_command(console: Console, root: Path, command: list[str], label: str) -> None:
    try:
        result = subprocess.run(
            command, cwd=root, capture_output=True, text=True, timeout=900, check=False,
        )
    except subprocess.TimeoutExpired:
        console.print(f"[red]{label} timed out after 15 minutes.[/red]")
        return
    except OSError as error:
        console.print(f"[red]Could not start {label.lower()}: {error}[/red]")
        return
    output = result.stdout.strip()
    errors = result.stderr.strip()
    if output:
        console.print(output)
    if errors:
        console.print(errors, style="dim" if result.returncode == 0 else "yellow")
    if result.returncode == 0:
        console.print(f"[green]{label} completed successfully.[/green]")
    else:
        console.print(f"[red]{label} failed with exit code {result.returncode}.[/red]")


def install_dependencies(console: Console, directory: Path | None = None) -> None:
    root = find_project_root(directory)
    if root is None or not ((root / "pyproject.toml").is_file() or (root / "requirements.txt").is_file()):
        console.print("[yellow]No Python dependency manifest found in a detected project.[/yellow]")
        return
    manifest = "pyproject.toml" if (root / "pyproject.toml").is_file() else "requirements.txt"
    python = project_python(root)
    command = [python, "-m", "pip", "install", "-e", "."] if manifest == "pyproject.toml" else [python, "-m", "pip", "install", "-r", "requirements.txt"]
    console.print(f"Project: {root}")
    console.print(f"Manifest: {manifest}")
    console.print(f"Proposed command: {' '.join(command)}")
    console.print("[yellow]This may download and install packages into the active Python environment.[/yellow]")
    if not typer.confirm("Run this installation command?", default=False):
        console.print("[dim]Installation cancelled. Nothing was installed.[/dim]")
        return
    _run_project_command(console, root, command, "Dependency installation")


def environment_report(console: Console) -> None:
    """Report selected variable presence only; never reveal values."""
    names = (
        "PATH", "HOME", "XDG_CONFIG_HOME", "VIRTUAL_ENV", "CONDA_PREFIX",
        "PYTHONPATH", "DATABASE_URL", "API_KEY", "OPENAI_API_KEY", "GITHUB_TOKEN",
    )
    table = Table(title="Environment variable presence · Values hidden")
    table.add_column("Variable")
    table.add_column("Status")
    for name in names:
        present = bool(os.environ.get(name))
        table.add_row(name, "[green]Set[/green]" if present else "[dim]Not set[/dim]")
    console.print(table)
    console.print("[dim]Only variable names and presence are shown; secret values were not read out.[/dim]")


def git_action_report(console: Console, action: str, directory: Path | None = None) -> None:
    """Run a read-only Git inspection action in the current repository."""
    if action == "status":
        from . import git_report
        git_report(console, directory)
        return
    actions = {
        "diff": ["diff", "--stat", "HEAD"],
        "log": ["log", "-10", "--oneline", "--decorate"],
        "branches": ["branch", "-vv"],
        "remotes": ["remote", "-v"],
    }
    if action not in actions:
        console.print("[yellow]Choose a Git action: status, diff, log, branches, remotes.[/yellow]")
        return
    target = (directory or Path.cwd()).expanduser().resolve()
    if not target.is_dir():
        console.print(f"[red]Directory does not exist: {target}[/red]")
        return
    try:
        root_result = subprocess.run(
            ["git", "-C", str(target), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        console.print(f"[yellow]Git is unavailable: {error}[/yellow]")
        return
    if root_result.returncode != 0:
        console.print(f"[yellow]No Git repository found from {target}.[/yellow]")
        return
    root = Path(root_result.stdout.strip())
    command = ["git", "-C", str(root), *actions[action]]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        console.print(f"[red]Git {action} failed: {error}[/red]")
        return
    console.print(f"\n[bold white]◈ ghost. / git {action}[/bold white]")
    console.print(f"[dim]{root}[/dim]")
    if result.returncode != 0:
        console.print(f"[yellow]Git exited with status {result.returncode}: {result.stderr.strip()}[/yellow]")
    elif result.stdout.strip():
        console.print(result.stdout.strip())
    else:
        console.print("[dim]No results.[/dim]")
