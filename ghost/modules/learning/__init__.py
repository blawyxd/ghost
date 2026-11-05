
from __future__ import annotations

import json
import copy
from pathlib import Path
from typing import Any
from datetime import date, datetime, timezone

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .curriculum import lessons_for
from .exercises import EXERCISES, edit_submission, run_exercise


CONFIG_DIR = Path.home() / ".config" / "ghost"
PROGRESS_FILE = CONFIG_DIR / "learning.json"

DEFAULT_DATA = {
    "game_mode": False,
    "xp": 0,
    "completed_lessons": [],
    "streak": 0,
    "achievements": [],
    "completed_exercises": [],
    "attempts": {},
    "mastery": {},
    "current_lesson": None,
    "assessment_results": [],
    "project_progress": {},
}


LESSONS = {
    "python-basics": {
        "title": "Python Basics",
        "description": "Variables, values and printing.",
        "content": [
            ("Variables", "A variable stores a value under a name."),
            ("Strings", "Strings are pieces of text, written inside quotes."),
            ("Integers", "Integers are whole numbers, such as 10 or -5."),
            ("Printing", "print() displays information in the terminal."),
        ],
        "challenge": "What function displays text in the terminal?",
        "answer": "print",
        "xp": 50,
    },
    "python-types": {
        "title": "Python Data Types",
        "description": "Understand the basic types of Python data.",
        "content": [
            ("Strings", "str represents text."),
            ("Integers", "int represents whole numbers."),
            ("Floats", "float represents decimal numbers."),
            ("Booleans", "bool represents True or False."),
        ],
        "challenge": "Which Python type represents decimal numbers?",
        "answer": "float",
        "xp": 50,
    },
    "python-conditionals": {
        "title": "Conditionals",
        "description": "Make programs respond to different conditions.",
        "content": [
            ("if", "Runs code when a condition is true."),
            ("elif", "Checks another condition if the previous one failed."),
            ("else", "Runs when none of the previous conditions matched."),
            ("Indentation", "Python uses indentation to define code blocks."),
        ],
        "challenge": "Which keyword runs code when an if condition is false and no other branch matched?",
        "answer": "else",
        "xp": 75,
    },
}


def load_progress() -> dict:
    if not PROGRESS_FILE.exists():
        return _normalise_progress({})

    try:
        data = json.loads(PROGRESS_FILE.read_text())
        if not isinstance(data, dict):
            raise ValueError("Invalid progress data")

        return _normalise_progress(data)

    except (json.JSONDecodeError, OSError, ValueError):
        return _normalise_progress({})


def _normalise_progress(data: dict[str, Any]) -> dict[str, Any]:
    """Add new fields while preserving all fields from older progress files."""
    progress = copy.deepcopy(DEFAULT_DATA)
    progress.update(data)
    progress["game_mode"] = progress.get("game_mode") is True
    for key in ("xp", "streak"):
        value = progress.get(key)
        progress[key] = value if type(value) is int and value >= 0 else DEFAULT_DATA[key]
    for key in ("completed_lessons", "achievements", "completed_exercises", "assessment_results"):
        if not isinstance(progress.get(key), list):
            progress[key] = []
    for key in ("completed_lessons", "achievements", "completed_exercises"):
        progress[key] = list(dict.fromkeys(item for item in progress[key] if isinstance(item, str)))
    for key in ("attempts", "mastery", "project_progress"):
        if not isinstance(progress.get(key), dict):
            progress[key] = {}
    progress["attempts"] = {
        exercise_id: count
        for exercise_id, count in progress["attempts"].items()
        if isinstance(exercise_id, str) and type(count) is int and count >= 0
    }
    progress["mastery"] = {
        topic: percentage
        for topic, percentage in progress["mastery"].items()
        if isinstance(topic, str) and type(percentage) is int and 0 <= percentage <= 100
    }
    if not isinstance(progress.get("current_lesson"), str):
        progress["current_lesson"] = None
    progress["assessment_results"] = [
        item for item in progress["assessment_results"] if isinstance(item, dict)
    ]
    legacy_ids = {
        "python-basics": "python-start",
        "python-types": "python-values",
        "python-conditionals": "python-expressions",
    }
    completed = progress["completed_lessons"]
    progress["completed_lessons"] = list(dict.fromkeys([
        *completed,
        *(new for old, new in legacy_ids.items() if old in completed),
    ]))
    return progress


def save_progress(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    temporary_file = PROGRESS_FILE.with_suffix(".tmp")
    temporary_file.write_text(json.dumps(data, indent=4), encoding="utf-8")
    temporary_file.replace(PROGRESS_FILE)


def game_mode_enabled() -> bool:
    return bool(load_progress()["game_mode"])


def award_xp(data: dict, amount: int) -> None:
    if not data["game_mode"]:
        return

    data["xp"] += amount
    console.print(f"\n[bold yellow]+{amount} XP[/bold yellow]")


def get_level(xp: int) -> int:
    return (xp // 100) + 1


def record_learning_day(data: dict[str, Any]) -> None:
    """Update a consecutive-day streak only while Game Mode is enabled."""
    if not data.get("game_mode"):
        return
    today = date.today()
    previous = data.get("last_activity_date")
    if previous == today.isoformat():
        return
    try:
        previous_day = date.fromisoformat(previous) if isinstance(previous, str) else None
    except ValueError:
        previous_day = None
    data["streak"] = data.get("streak", 0) + 1 if previous_day == today.fromordinal(today.toordinal() - 1) else 1
    data["last_activity_date"] = today.isoformat()
    console.print(f"[yellow]Learning streak: {data['streak']} day(s)[/yellow]")


def update_achievements(data: dict) -> None:
    achievements = {
        "first-lesson": (
            len(data["completed_lessons"]) >= 1,
            "First Steps",
        ),
        "five-lessons": (
            len(data["completed_lessons"]) >= 5,
            "Getting Serious",
        ),
        "one-thousand-xp": (
            data["xp"] >= 1000,
            "XP Collector",
        ),
    }

    for achievement_id, (unlocked, name) in achievements.items():
        if unlocked and achievement_id not in data["achievements"]:
            data["achievements"].append(achievement_id)
            console.print(
                f"[bold green]Achievement unlocked: {name}![/bold green]"
            )


def learning_settings(console: Console, mode: str) -> None:
    data = load_progress()

    if mode == "on":
        data["game_mode"] = True
        save_progress(data)
        console.print("[bold green]Game Mode enabled.[/bold green]")
        console.print("[dim]XP, levels and achievements are now active.[/dim]")

    elif mode == "off":
        data["game_mode"] = False
        save_progress(data)
        console.print("[bold yellow]Game Mode disabled.[/bold yellow]")
        console.print("[dim]Your saved XP and achievements are preserved.[/dim]")

    elif mode == "status":
        status = "Enabled" if data["game_mode"] else "Disabled"
        console.print(f"Game Mode: [bold]{status}[/bold]")
        completed = sum(
            1 for lesson in lessons_for()
            if set(lesson.exercise_ids).issubset(data["completed_exercises"])
        )
        console.print(f"Completed lessons: {completed}")
        if data["game_mode"]:
            console.print(f"Saved XP: {data['xp']}")
            console.print(f"Level: {get_level(data['xp'])}")
            console.print(f"Achievements: {len(data['achievements'])}")
            console.print(f"Learning streak: {data['streak']} day(s)")

    else:
        console.print("[red]Use: ghost learning on, off or status[/red]")


def progress_report(console: Console) -> None:
    data = load_progress()
    lessons = lessons_for()
    completed_exercises = set(data["completed_exercises"])
    exercise_ids = list(dict.fromkeys(
        exercise_id for lesson in lessons for exercise_id in lesson.exercise_ids
    ))

    table = Table(title="Learning Progress")
    table.add_column("Statistic")
    table.add_column("Value", justify="right")

    table.add_row("Game Mode", "ON" if data["game_mode"] else "OFF")
    completed_count = sum(
        1 for lesson in lessons
        if set(lesson.exercise_ids).issubset(completed_exercises)
    )
    table.add_row("Completed lessons", str(completed_count))
    table.add_row("Completed exercises", str(len(data["completed_exercises"])))
    percent = round(completed_count / len(lessons) * 100) if lessons else 0
    table.add_row("Course progress", f"{percent}%")
    table.add_row("Exercises remaining", str(len(set(exercise_ids) - completed_exercises)))
    next_exercise = next((
        exercise_id for lesson in lessons for exercise_id in lesson.exercise_ids
        if exercise_id not in completed_exercises
    ), None)
    table.add_row("Next exercise", next_exercise or "All course exercises complete")
    table.add_row("Current lesson", data.get("current_lesson") or "Not set")
    project_records = data.get("project_progress", {})
    started = sum(
        1 for record in project_records.values()
        if isinstance(record, dict) and record.get("completed_milestones")
    )
    finished = sum(
        1 for record in project_records.values()
        if isinstance(record, dict) and record.get("completed")
    )
    table.add_row("Projects started / completed", f"{started} / {finished}")
    if data["game_mode"]:
        table.add_row("XP", str(data["xp"]))
        table.add_row("Level", str(get_level(data["xp"])))
        table.add_row("Achievements", str(len(data["achievements"])))
        table.add_row("Learning streak", f"{data['streak']} day(s)")
    if data["assessment_results"]:
        latest = data["assessment_results"][-1]
        result = "Passed" if latest.get("passed") else "Needs work"
        table.add_row("Last assessment", f"{latest.get('exercise_id', 'unknown')} · {result}")

    console.print(table)

    topic_exercises: dict[str, list[str]] = {}
    for lesson in lessons:
        topic_exercises.setdefault(lesson.topic, []).extend(lesson.exercise_ids)
    mastery_table = Table(title="Topic mastery")
    mastery_table.add_column("Topic")
    mastery_table.add_column("Exercises passed", justify="right")
    mastery_table.add_column("Mastery", justify="right")
    for topic, ids in topic_exercises.items():
        unique_ids = list(dict.fromkeys(ids))
        passed = len(set(unique_ids) & completed_exercises)
        percentage = round(passed / len(unique_ids) * 100) if unique_ids else 0
        mastery_table.add_row(topic.title(), f"{passed}/{len(unique_ids)}", f"{percentage}%")
    console.print(mastery_table)


def learn(console: Console, lesson_id: str | None = None) -> None:
    data = load_progress()

    console.print(
        Panel(
            "[bold white]◈ ghost. learning[/bold white]\n"
            "[dim]Learn programming one step at a time.[/dim]",
            border_style="blue",
        )
    )

    table = Table()
    table.add_column("#", justify="right")
    table.add_column("Lesson")
    table.add_column("Description")
    table.add_column("Status")

    lessons = lessons_for()
    completed_exercises = set(data["completed_exercises"])
    attempted_exercises = set(data["attempts"])
    for index, lesson in enumerate(lessons, 1):
        completed_count = len(set(lesson.exercise_ids) & completed_exercises)
        total_count = len(lesson.exercise_ids)
        if completed_count == total_count:
            status = f"[green]Completed ({total_count}/{total_count})[/green]"
        elif lesson.id in data["completed_lessons"]:
            status = f"[yellow]Prior completion · practice ({completed_count}/{total_count})[/yellow]"
        elif completed_count or attempted_exercises.intersection(lesson.exercise_ids) or data.get("current_lesson") == lesson.id:
            status = f"[yellow]In progress ({completed_count}/{total_count})[/yellow]"
        else:
            status = "[dim]Not started[/dim]"
        table.add_row(
            str(index),
            f"{lesson.id} · {lesson.title}",
            lesson.description,
            status,
        )

    console.print(table)

    if lesson_id is None:
        lesson_id = typer.prompt("Enter a lesson number or ID ('next' for the suggested lesson, 'exit' to leave)")

    if lesson_id.lower() == "exit":
        return

    if lesson_id.lower() == "next":
        lesson_id = next((
            item.id for item in lessons
            if not set(item.exercise_ids).issubset(data["completed_exercises"])
        ), "")
        if not lesson_id:
            console.print("[green]You have completed every course lesson.[/green]")
            return

    if lesson_id.isdecimal():
        lesson_number = int(lesson_id)
        if not 1 <= lesson_number <= len(lessons):
            console.print(f"[yellow]Choose a lesson number from 1 to {len(lessons)}.[/yellow]")
            return
        lesson_id = lessons[lesson_number - 1].id

    lesson_id = {
        "python-basics": "python-start",
        "python-types": "python-values",
        "python-conditionals": "python-expressions",
    }.get(lesson_id, lesson_id)
    lesson = next((item for item in lessons if item.id == lesson_id), None)

    if lesson is None:
        console.print("[red]That lesson doesn't exist.[/red]")
        console.print("Use a lesson number, lesson ID, or 'next'.")
        return

    lesson_index = lessons.index(lesson)
    suggested = next((
        item for item in lessons
        if not set(item.exercise_ids).issubset(data["completed_exercises"])
    ), None)
    if suggested is not None and lesson_index > lessons.index(suggested):
        console.print(
            f"[dim]Suggested next lesson: {suggested.id} · {suggested.title}. "
            "You can still open lessons in any order.[/dim]"
        )

    data["current_lesson"] = lesson.id
    save_progress(data)

    console.print(
        Panel(
            f"[bold]{lesson.title}[/bold]\n{lesson.description}",
            border_style="blue",
        )
    )

    for heading, explanation in lesson.explanations:
        console.print(f"\n[bold cyan]{heading}[/bold cyan]")
        console.print(explanation)
    for index, ((heading, code), walkthrough, language) in enumerate(
        zip(lesson.examples, lesson.example_walkthroughs, lesson.example_languages), 1
    ):
        console.print(f"\n[bold cyan]Example {index}: {heading}[/bold cyan] [dim]({language})[/dim]")
        console.print(Panel(code, border_style="dim"))
        console.print(f"[dim]Why it works:[/dim] {walkthrough}")
    console.print("\n[bold cyan]Common mistakes[/bold cyan]")
    for mistake, fix in lesson.mistakes:
        console.print(f"[yellow]{mistake}[/yellow]\n{fix}")
    console.print("\n[bold cyan]Recap[/bold cyan]")
    for item in lesson.recap:
        console.print(f"• {item}")
    console.print("\n[bold]Coding practice[/bold]")
    exercise_table = Table()
    exercise_table.add_column("Exercise")
    exercise_table.add_column("Difficulty")
    exercise_table.add_column("Status")
    exercise_table.add_column("Command")
    next_exercise = None
    for exercise_id in lesson.exercise_ids:
        exercise = EXERCISES.get(exercise_id)
        if exercise is None:
            continue
        is_complete = exercise_id in data["completed_exercises"]
        if not is_complete and next_exercise is None:
            next_exercise = exercise_id
        exercise_table.add_row(
            f"{exercise.id} · {exercise.title}",
            exercise.difficulty,
            "[green]Completed[/green]" if is_complete else "[dim]Available[/dim]",
            f"ghost exercise {exercise.id}",
        )
    console.print(exercise_table)
    if next_exercise:
        console.print(f"Next: [cyan]ghost exercise {next_exercise}[/cyan]")
    else:
        console.print("[green]All coding exercises for this lesson are complete.[/green]")


def exercises_report(console: Console) -> None:
    """List curriculum exercises with difficulty and completion state."""
    data = load_progress()
    table = Table(title="Python coding exercises")
    table.add_column("Lesson")
    table.add_column("Exercise")
    table.add_column("Difficulty")
    table.add_column("Status")
    for lesson in lessons_for():
        for exercise_id in lesson.exercise_ids:
            exercise = EXERCISES.get(exercise_id)
            if exercise is None:
                continue
            status = "[green]Completed[/green]" if exercise_id in data["completed_exercises"] else "[dim]Available[/dim]"
            table.add_row(lesson.title, f"{exercise.id} · {exercise.title}", exercise.difficulty, status)
    console.print(table)
    console.print("Run [cyan]ghost exercise <id>[/cyan] to work on one.")


def exercise_command(
    console: Console,
    exercise_id: str,
    source_file: Path | None = None,
    show_solution: bool = False,
    hint_number: int | None = None,
) -> None:
    exercise = EXERCISES.get(exercise_id)
    if exercise is None:
        console.print(f"[red]Unknown exercise '{exercise_id}'.[/red]")
        console.print("Available: " + ", ".join(EXERCISES))
        return
    data = load_progress()
    if hint_number is not None:
        if hint_number < 1 or hint_number > len(exercise.hints):
            console.print(f"[yellow]Choose a hint from 1 to {len(exercise.hints)}.[/yellow]")
            return
        console.print(Panel(exercise.hints[hint_number - 1], title=f"Hint {hint_number} · {exercise.title}"))
        return
    console.print(Panel(
        f"[bold]{exercise.title}[/bold] · {exercise.difficulty}\n{exercise.instructions}\n\n"
        "Starter code:\n" + exercise.starter,
        title=f"Exercise {exercise.id}", border_style="blue",
    ))
    console.print(
        "[dim]Submissions run in a separate timed process, not a security sandbox. "
        "Only run code you trust.[/dim]"
    )
    if show_solution:
        if exercise_id not in data["completed_exercises"] and not typer.confirm(
            "You have not completed this exercise. Show the solution anyway?", default=False
        ):
            return
        console.print(Panel(exercise.solution, title="Solution"))
        return
    if source_file is not None:
        try:
            source = source_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            console.print(f"[red]Could not read submission: {error}[/red]")
            return
    else:
        source = edit_submission(exercise)
        if source is None:
            console.print("[yellow]No editor opened. Set EDITOR or pass --file PATH.[/yellow]")
            console.print(f"Copy the starter into a .py file, implement it, then run: ghost exercise {exercise.id} --file your_answer.py")
            return
    passed, message = run_exercise(exercise, source)
    attempt_number = data["attempts"].get(exercise_id, 0) + 1
    data["attempts"][exercise_id] = attempt_number
    data["assessment_results"].append({
        "exercise_id": exercise_id,
        "attempt": attempt_number,
        "passed": passed,
        "result": message,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    })
    if passed:
        console.print(f"[bold green]Passed![/bold green] {message}")
        new_exercise = exercise_id not in data["completed_exercises"]
        if new_exercise:
            data["completed_exercises"].append(exercise_id)
        data["mastery"][exercise_id] = 100
        completed_lessons = []
        for lesson in lessons_for():
            if (
                exercise_id in lesson.exercise_ids
                and set(lesson.exercise_ids).issubset(data["completed_exercises"])
                and lesson.id not in data["completed_lessons"]
            ):
                data["completed_lessons"].append(lesson.id)
                completed_lessons.append(lesson)
        topic_exercises: dict[str, set[str]] = {}
        for lesson in lessons_for():
            topic_exercises.setdefault(lesson.topic, set()).update(lesson.exercise_ids)
        for topic, exercise_ids in topic_exercises.items():
            passed_count = len(exercise_ids & set(data["completed_exercises"]))
            data["mastery"][topic] = round(passed_count / len(exercise_ids) * 100) if exercise_ids else 0
        if data["game_mode"] and (new_exercise or completed_lessons):
            if new_exercise:
                award_xp(data, 25)
            for _ in completed_lessons:
                award_xp(data, 20)
            record_learning_day(data)
            update_achievements(data)
    else:
        console.print(f"[bold red]Not passed:[/bold red] {message}")
        hint_index = min(data["attempts"][exercise_id] - 1, len(exercise.hints) - 1)
        console.print(f"[cyan]Hint {hint_index + 1}:[/cyan] {exercise.hints[hint_index]}")
    save_progress(data)


def glossary(console: Console) -> None:
    terms = {
        "Variable": "A named place to store data.",
        "String": "A data type used for text.",
        "Integer": "A whole number.",
        "Float": "A decimal number.",
        "Boolean": "A value that is either True or False.",
        "Function": "Reusable code that performs a task.",
        "Condition": "An expression evaluated as True or False.",
    }

    console.print("\n[bold]◈ Programming glossary[/bold]\n")

    for term, definition in terms.items():
        console.print(f"[bold cyan]{term}[/bold cyan]")
        console.print(f"  {definition}\n")


def cheatsheet(console: Console) -> None:
    console.print(
        Panel(
            "[bold cyan]Python[/bold cyan]\n\n"
            "print('Hello')  - Display text\n"
            "name = 'Blawy' - Store a string\n"
            "age = 16        - Store an integer\n"
            "if age > 10:    - Check a condition\n"
            "else:           - Alternative branch\n"
            "for i in range(5): - Repeat code\n"
            "def greet():   - Define a function",
            title="Quick Cheatsheet",
            border_style="blue",
        )
    )


console = Console()
