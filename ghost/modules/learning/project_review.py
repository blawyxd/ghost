"""Read-only structural checks for learner-built project directories."""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .projects import Project


@dataclass(frozen=True)
class ReviewCheck:
    name: str
    status: str
    details: str


IGNORED_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", ".tox"}


def inspect_project(project: Project, directory: Path) -> tuple[ReviewCheck, ...]:
    """Inspect expected project structure and Python syntax without executing code."""
    root = directory.expanduser()
    if not root.is_dir():
        return (ReviewCheck("Project directory", "FAIL", f"Not a directory: {root}"),)

    python_files: list[Path] = []
    test_files: list[Path] = []
    for current, dirs, filenames in os.walk(root, followlinks=False):
        dirs[:] = [name for name in dirs if name not in IGNORED_DIRS and not (Path(current) / name).is_symlink()]
        for filename in filenames:
            candidate = Path(current) / filename
            if candidate.is_symlink() or candidate.suffix != ".py" or not candidate.is_file():
                continue
            python_files.append(candidate)
            if filename.startswith("test_") or filename.endswith("_test.py") or "tests" in candidate.relative_to(root).parts[:-1]:
                test_files.append(candidate)

    checks = [
        ReviewCheck(
            "Python source",
            "PASS" if python_files else "FAIL",
            f"Found {len(python_files)} Python source file(s)." if python_files else "No Python source files found.",
        ),
        ReviewCheck(
            "Test files",
            "PASS" if test_files else "FAIL",
            f"Found {len(test_files)} likely test file(s)." if test_files else "No test files found (use tests/ or test_*.py).",
        ),
    ]

    syntax_errors: list[str] = []
    for source_file in python_files:
        try:
            ast.parse(source_file.read_text(encoding="utf-8"), filename=str(source_file.relative_to(root)))
        except (OSError, UnicodeError, SyntaxError) as error:
            syntax_errors.append(f"{source_file.relative_to(root)}: {error}")
    checks.append(ReviewCheck(
        "Python syntax",
        "PASS" if python_files and not syntax_errors else "FAIL",
        "All Python files parse successfully." if python_files and not syntax_errors
        else "; ".join(syntax_errors) if syntax_errors else "Cannot check syntax without Python source files.",
    ))

    if project.id == "modular-service":
        metadata = root / "pyproject.toml"
        checks.append(ReviewCheck(
            "Build metadata",
            "PASS" if metadata.is_file() and not metadata.is_symlink() else "FAIL",
            "Found pyproject.toml." if metadata.is_file() and not metadata.is_symlink()
            else "This project requires pyproject.toml.",
        ))
    else:
        readme = next((root / name for name in ("README.md", "README.rst", "README.txt") if (root / name).is_file()), None)
        checks.append(ReviewCheck(
            "Usage documentation",
            "PASS" if readme else "INFO",
            f"Found {readme.name}." if readme else "No README found; document setup and usage before sharing the project.",
        ))
    return tuple(checks)


def review_project(console: Console, project: Project, directory: Path) -> None:
    checks = inspect_project(project, directory)
    table = Table(title=f"Project review · {project.title}")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Details")
    for check in checks:
        style = {"PASS": "green", "FAIL": "red", "INFO": "yellow"}[check.status]
        table.add_row(check.name, f"[{style}]{check.status}[/{style}]", check.details)
    console.print(table)
    if any(check.status == "FAIL" for check in checks):
        console.print("[yellow]Review has required checks to address. The project is not executed and milestones are unchanged.[/yellow]")
    else:
        console.print("[green]Structural checks passed. Review the project acceptance criteria and run its tests separately.[/green]")
