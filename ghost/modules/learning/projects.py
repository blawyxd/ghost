"""Progressive application projects with concrete, reviewable milestones."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import award_xp, load_progress, record_learning_day, save_progress, update_achievements


@dataclass(frozen=True)
class Project:
    id: str
    title: str
    difficulty: str
    brief: str
    concepts: tuple[str, ...]
    milestones: tuple[str, ...]
    acceptance: tuple[str, ...]
    lessons: tuple[str, ...]


PROJECTS: tuple[Project, ...] = (
    Project(
        "calculator", "Command-line calculator", "Beginner",
        "Build a calculator that reads expressions, performs supported operations, and keeps prompting until the user exits.",
        ("input/output", "numeric conversion", "conditions", "functions", "exceptions"),
        ("Write functions for addition, subtraction, multiplication, and division.",
         "Prompt for two numbers and an operation; validate the operation.",
         "Handle invalid numbers and division by zero without crashing.",
         "Repeat calculations until the user chooses to quit.",
         "Add tests for each operation and its failure cases."),
        ("A user can perform all four operations.", "Invalid input produces a useful message.",
         "Division by zero is handled.", "The program can exit cleanly.", "Tests run without interactive input."),
        ("python-io", "python-conditions", "python-functions", "python-errors", "python-tests"),
    ),
    Project(
        "guessing-game", "Number guessing game", "Beginner",
        "Create a replayable game that chooses a secret number and guides guesses with higher/lower feedback.",
        ("random numbers", "loops", "conditions", "input validation", "state"),
        ("Choose a random target within a documented range.",
         "Read guesses and report whether each is too high, too low, or correct.",
         "Reject non-numeric and out-of-range guesses safely.",
         "Count attempts and report the score at the end of a round.",
         "Offer another round and test game logic with an injected target."),
        ("Each round has one target and ends on a correct guess.", "Bad input does not crash the game.",
         "Attempt count is accurate.", "Randomness can be controlled in tests."),
        ("python-conditions", "python-loops", "python-functions", "python-tests"),
    ),
    Project(
        "todo-cli", "Persistent to-do CLI", "Beginner → intermediate",
        "Build a command-line task manager that stores tasks between runs using a JSON file.",
        ("lists and dictionaries", "JSON", "files", "functions", "CLI design", "testing"),
        ("Define a task record with an ID, title, and completion state.",
         "Implement add, list, complete, and remove operations as separate functions.",
         "Load and save data as JSON, handling a missing or malformed file.",
         "Support commands and arguments using argparse.",
         "Test data operations with a temporary storage path."),
        ("Tasks remain after restarting.", "Unknown task IDs are reported without data loss.",
         "Malformed storage is handled with a clear error.", "Tests never modify the user's real task file."),
        ("python-collections", "python-json-api", "python-files", "python-modules", "python-tests"),
    ),
    Project(
        "file-organiser", "Safe file organiser", "Intermediate",
        "Sort files into type-based folders while previewing every planned move before changing anything.",
        ("pathlib", "file metadata", "dictionaries", "CLI options", "safety checks", "tests"),
        ("Scan only a directory supplied by the user; do not recurse unless requested.",
         "Classify files by extension and plan destination paths.",
         "Detect name collisions and report how each will be handled.",
         "Add a dry-run mode that lists every move and estimated affected file count.",
         "Require an explicit --apply option before performing moves.",
         "Test against temporary directories, including collisions and symlinks."),
        ("Default execution changes no files.", "Every planned move is previewed.",
         "Existing files are never silently overwritten.", "The applied run matches the preview."),
        ("python-files", "python-collections", "python-errors", "python-tests", "python-architecture"),
    ),
    Project(
        "log-inspector", "Log inspector CLI", "Intermediate",
        "Summarise a text log by severity and time range, with options to filter and export a report.",
        ("streaming files", "strings", "dictionaries", "argument parsing", "error handling"),
        ("Read a log one line at a time so large files do not need to fit in memory.",
         "Parse timestamps and severity labels; count entries by severity.",
         "Add filters for a time range and minimum severity.",
         "Show the most common error messages without exposing unrelated file contents.",
         "Export a summary as JSON and test malformed lines."),
        ("Large inputs are processed incrementally.", "Malformed lines are counted and skipped or reported.",
         "Filters have boundary tests.", "JSON output can be parsed by another program."),
        ("python-strings", "python-iterators", "python-json-api", "python-tests"),
    ),
    Project(
        "api-client", "API client", "Intermediate",
        "Build a command-line client for a public JSON API with timeouts, clear errors, and cached responses.",
        ("HTTP", "JSON", "environment variables", "timeouts", "caching", "testing"),
        ("Choose an API and document its terms and data fields.",
         "Write a client function with a timeout and explicit status/error handling.",
         "Convert the response JSON into a small internal data model.",
         "Read any API token from an environment variable; never print or commit it.",
         "Add a local cache with an expiry time and test using mocked responses."),
        ("Network errors and invalid JSON produce useful messages.", "Requests have finite timeouts.",
         "Secrets are not hard-coded or included in logs.", "Tests do not require a live network."),
        ("python-json-api", "python-errors", "python-modules", "python-tests", "python-architecture"),
    ),
    Project(
        "reading-list", "SQLite reading-list application", "Intermediate → advanced",
        "Create a persistent book tracker with a SQLite database, migrations, search, and a tested CLI.",
        ("SQLite", "SQL parameters", "classes or data classes", "modules", "transactions", "tests"),
        ("Design a books table with title, author, status, and timestamps.",
         "Implement add, list, search, and status-change operations using parameterised SQL.",
         "Keep database access in a repository module separate from CLI output.",
         "Add a schema version and a safe migration path.",
         "Test against a temporary database and verify rollback on failed writes."),
        ("Search input cannot alter SQL structure.", "Data survives process restarts.",
         "A failed write does not leave a partial update.", "CLI logic can be tested without a real terminal."),
        ("python-classes", "python-modules", "python-errors", "python-tests", "python-architecture"),
    ),
    Project(
        "modular-service", "Modular service with tests and packaging", "Advanced",
        "Turn a useful data-processing tool into a small distributable Python application with a stable command-line interface.",
        ("package layout", "type hints", "design boundaries", "logging", "testing", "build metadata"),
        ("Write a short requirements document and define the command interface.",
         "Separate domain logic, file/database adapters, and CLI registration into modules.",
         "Add type hints and unit tests for domain rules plus integration tests for adapters.",
         "Add structured logging to stderr while keeping machine-readable output on stdout.",
         "Declare dependencies and an entry point in pyproject.toml.",
         "Build a wheel, install it in a clean virtual environment, and test the installed command."),
        ("A clean environment can install and run the command.", "Core rules do not depend on the terminal.",
         "Tests cover success, invalid input, and storage failures.", "The README gives install and usage examples."),
        ("python-type-hints", "python-packages", "python-tests", "python-architecture", "python-performance"),
    ),
)


def projects_report(
    console: Console,
    project_id: str | None = None,
    complete_milestone: int | None = None,
    review_path: Path | None = None,
) -> None:
    data = load_progress()
    progress = data.setdefault("project_progress", {})
    if project_id is None:
        if review_path is not None:
            console.print("[red]Choose a project ID before requesting a project review.[/red]")
            return
        table = Table(title="Python project path")
        table.add_column("ID")
        table.add_column("Project")
        table.add_column("Difficulty")
        table.add_column("Progress", justify="right")
        for project in PROJECTS:
            record = progress.get(project.id, {})
            completed = record.get("completed_milestones", []) if isinstance(record, dict) else []
            if not isinstance(completed, list):
                completed = []
            completed = {
                number for number in completed
                if type(number) is int and 1 <= number <= len(project.milestones)
            }
            percent = round(len(completed) / len(project.milestones) * 100)
            table.add_row(project.id, project.title, project.difficulty, f"{percent}%")
        console.print(table)
        console.print("\nOpen one with: ghost projects PROJECT_ID")
        return

    project = next((item for item in PROJECTS if item.id == project_id), None)
    if project is None:
        console.print(f"[red]Unknown project '{project_id}'.[/red]")
        console.print("Available: " + ", ".join(item.id for item in PROJECTS))
        return
    record = progress.get(project.id)
    if not isinstance(record, dict):
        record = {"completed_milestones": [], "completed": False}
        progress[project.id] = record
    completed = record.setdefault("completed_milestones", [])
    if not isinstance(completed, list):
        completed = []
        record["completed_milestones"] = completed
    completed[:] = sorted({
        number for number in completed
        if type(number) is int and 1 <= number <= len(project.milestones)
    })
    if complete_milestone is not None:
        if not 1 <= complete_milestone <= len(project.milestones):
            console.print(f"[red]Milestone must be between 1 and {len(project.milestones)}.[/red]")
            return
        next_expected = next((
            number for number in range(1, len(project.milestones) + 1)
            if number not in completed
        ), None)
        if complete_milestone not in completed and complete_milestone != next_expected:
            console.print(
                f"[yellow]Complete milestone {next_expected} first; project steps build on one another.[/yellow]"
            )
            return
        if complete_milestone not in completed:
            completed.append(complete_milestone)
            completed.sort()
            record["last_updated"] = datetime.now(timezone.utc).isoformat()
            record["completed"] = len(completed) == len(project.milestones)
            if data.get("game_mode"):
                award_xp(data, 15)
                record_learning_day(data)
                update_achievements(data)
            save_progress(data)
            console.print(f"[green]Milestone {complete_milestone} marked complete.[/green]")

    done = set(completed)
    console.print(Panel(
        f"[bold]{project.title}[/bold] · {project.difficulty}\n{project.brief}",
        border_style="blue",
    ))
    console.print("[bold cyan]Concepts used[/bold cyan]: " + ", ".join(project.concepts))
    console.print("\n[bold]Milestones[/bold]")
    for number, milestone in enumerate(project.milestones, 1):
        status = "[green]✓[/green]" if number in done else "[dim]○[/dim]"
        console.print(f"{status} {number}. {milestone}")
    console.print("\n[bold]Definition of done[/bold]")
    for item in project.acceptance:
        console.print(f"• {item}")
    console.print("\n[bold]Related lessons[/bold]: " + ", ".join(project.lessons))
    if review_path is not None:
        from .project_review import review_project

        review_project(console, project, review_path)
    is_complete = set(range(1, len(project.milestones) + 1)).issubset(done)
    if is_complete:
        console.print("\n[bold green]Project milestones complete.[/bold green]")
    else:
        next_milestone = next((i for i in range(1, len(project.milestones) + 1) if i not in done), None)
        console.print(f"\nTrack a finished milestone with: ghost projects {project.id} --complete-milestone {next_milestone}")
