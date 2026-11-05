from __future__ import annotations

import ast
import json
from io import StringIO
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from rich.console import Console

from ghost.modules.learning import (
    _normalise_progress, exercise_command, exercises_report, learn, load_progress,
    progress_report, record_learning_day, save_progress,
)
from ghost.modules.learning.exercises import EXERCISES, run_exercise
from ghost.modules.learning.curriculum import lessons_for


class LearningProgressTests(unittest.TestCase):
    def test_streak_changes_only_when_gamification_is_enabled(self) -> None:
        disabled = {"game_mode": False, "streak": 6, "last_activity_date": None}
        record_learning_day(disabled)
        self.assertEqual(disabled["streak"], 6)
        enabled = {
            "game_mode": True,
            "streak": 6,
            "last_activity_date": (date.today() - timedelta(days=1)).isoformat(),
        }
        with patch("ghost.modules.learning.console", Console(file=StringIO())):
            record_learning_day(enabled)
        self.assertEqual(enabled["streak"], 7)

    def test_legacy_progress_is_preserved_and_extended(self) -> None:
        old = {
            "game_mode": False,
            "xp": 325,
            "completed_lessons": ["python-basics"],
            "streak": 4,
            "achievements": ["first-lesson"],
        }
        progress = _normalise_progress(old)
        self.assertEqual(progress["xp"], 325)
        self.assertEqual(progress["streak"], 4)
        self.assertIn("python-start", progress["completed_lessons"])
        self.assertEqual(progress["completed_exercises"], [])

    def test_legacy_lesson_credit_does_not_skip_new_required_coding_practice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("ghost.modules.learning.CONFIG_DIR", root), patch(
                "ghost.modules.learning.PROGRESS_FILE", root / "learning.json"
            ):
                save_progress({"completed_lessons": ["python-basics"]})
                output = StringIO()
                with patch("ghost.modules.learning.typer.prompt", return_value="next"):
                    learn(Console(file=output), None)
                data = load_progress()
                self.assertEqual(data["current_lesson"], "python-start")
                self.assertIn("python-start", data["completed_lessons"])
                self.assertIn("Prior completion", output.getvalue())
                self.assertIn("hello_program", output.getvalue())

    def test_progress_normalization_sanitizes_bad_types_and_preserves_unknown_fields(self) -> None:
        progress = _normalise_progress({
            "game_mode": "false",
            "xp": "500",
            "streak": True,
            "completed_lessons": ["python-start", 12, "python-start"],
            "attempts": {"greeting": "many", "profile": 2},
            "mastery": {"variables": 150, "functions": 75, 3: 100},
            "legacy_note": "keep this field",
        })
        self.assertFalse(progress["game_mode"])
        self.assertEqual(progress["xp"], 0)
        self.assertEqual(progress["streak"], 0)
        self.assertEqual(progress["completed_lessons"], ["python-start"])
        self.assertEqual(progress["attempts"], {"profile": 2})
        self.assertEqual(progress["mastery"], {"functions": 75})
        self.assertEqual(progress["legacy_note"], "keep this field")

    def test_load_and_save_use_persistent_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("ghost.modules.learning.CONFIG_DIR", root), patch(
                "ghost.modules.learning.PROGRESS_FILE", root / "learning.json"
            ):
                save_progress({"game_mode": True, "xp": 75, "completed_lessons": []})
                loaded = load_progress()
                self.assertTrue(loaded["game_mode"])
                self.assertEqual(loaded["xp"], 75)
                self.assertTrue((root / "learning.json").is_file())
                self.assertIsInstance(json.loads((root / "learning.json").read_text()), dict)

    def test_default_progress_nested_state_is_not_shared(self) -> None:
        first = _normalise_progress({})
        first["attempts"]["greeting"] = 2
        first["completed_lessons"].append("python-start")
        second = _normalise_progress({})
        self.assertEqual(second["attempts"], {})
        self.assertEqual(second["completed_lessons"], [])

    def test_progress_report_shows_partial_mastery_and_next_exercise(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("ghost.modules.learning.CONFIG_DIR", root), patch(
                "ghost.modules.learning.PROGRESS_FILE", root / "learning.json"
            ):
                save_progress({
                    "game_mode": False,
                    "completed_exercises": ["hello_program"],
                    "attempts": {"two_greetings": 1},
                })
                output = StringIO()
                progress_report(Console(file=output))
                report = output.getvalue()
                self.assertIn("Exercises remaining", report)
                self.assertIn("two_greetings", report)
                self.assertIn("Fundamentals", report)
                self.assertIn("1/2", report)
                self.assertNotIn("XP", report)
                self.assertNotIn("Level", report)

    def test_opening_lesson_tracks_current_lesson(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("ghost.modules.learning.CONFIG_DIR", root), patch(
                "ghost.modules.learning.PROGRESS_FILE", root / "learning.json"
            ):
                output = StringIO()
                learn(Console(file=output), "python-conditions")
                self.assertEqual(load_progress()["current_lesson"], "python-conditions")
                self.assertNotIn("python-conditions", load_progress()["completed_lessons"])
                output = StringIO()
                with patch("ghost.modules.learning.typer.prompt", return_value="exit"):
                    learn(Console(file=output))
                self.assertIn("In progress (0/1)", output.getvalue())

    def test_lesson_lists_every_exercise_and_points_to_next_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("ghost.modules.learning.CONFIG_DIR", root), patch(
                "ghost.modules.learning.PROGRESS_FILE", root / "learning.json"
            ):
                save_progress({"completed_exercises": ["hello_program"]})
                output = StringIO()
                learn(Console(file=output), "python-start")
                rendered = output.getvalue()
                self.assertIn("hello_program", rendered)
                self.assertIn("two_greetings", rendered)
                self.assertIn("Next: ghost exercise two_greetings", rendered)

    def test_lesson_browser_accepts_course_numbers_and_next(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("ghost.modules.learning.CONFIG_DIR", root), patch(
                "ghost.modules.learning.PROGRESS_FILE", root / "learning.json"
            ), patch("ghost.modules.learning.typer.prompt", return_value="1"):
                output = StringIO()
                learn(Console(file=output), None)
                self.assertEqual(load_progress()["current_lesson"], "python-start")

            with patch("ghost.modules.learning.CONFIG_DIR", root), patch(
                "ghost.modules.learning.PROGRESS_FILE", root / "learning.json"
            ), patch("ghost.modules.learning.typer.prompt", return_value="next"):
                learn(Console(file=StringIO()), None)
                self.assertEqual(load_progress()["current_lesson"], "python-start")

    def test_lesson_browser_suggests_order_without_locking_lessons(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("ghost.modules.learning.CONFIG_DIR", root), patch(
                "ghost.modules.learning.PROGRESS_FILE", root / "learning.json"
            ):
                output = StringIO()
                learn(Console(file=output), "python-projects")
                self.assertEqual(load_progress()["current_lesson"], "python-projects")
                self.assertIn("Suggested next lesson: python-start", output.getvalue())

    def test_passing_exercise_completes_its_lesson_and_mastery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            progress_file = root / "learning.json"
            with patch("ghost.modules.learning.CONFIG_DIR", root), patch(
                "ghost.modules.learning.PROGRESS_FILE", progress_file
            ):
                for exercise_id in ("classify", "shipping_cost"):
                    source_file = root / f"{exercise_id}.py"
                    source_file.write_text(EXERCISES[exercise_id].solution, encoding="utf-8")
                    exercise_command(Console(file=StringIO()), exercise_id, source_file)
                    if exercise_id == "classify":
                        self.assertNotIn("python-function-decisions", load_progress()["completed_lessons"])
                data = load_progress()
                self.assertIn("python-function-decisions", data["completed_lessons"])
                self.assertEqual(data["mastery"]["functions"], 29)
                self.assertIn("classify", data["completed_exercises"])

    def test_lesson_with_multiple_exercises_completes_after_all_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("ghost.modules.learning.CONFIG_DIR", root), patch(
                "ghost.modules.learning.PROGRESS_FILE", root / "learning.json"
            ):
                for exercise_id in ("greeting", "profile", "is_even"):
                    source_file = root / f"{exercise_id}.py"
                    source_file.write_text(EXERCISES[exercise_id].solution, encoding="utf-8")
                    exercise_command(Console(file=StringIO()), exercise_id, source_file)
                    completed = load_progress()["completed_lessons"]
                    if exercise_id != "is_even":
                        self.assertNotIn("python-functions", completed)
                data = load_progress()
                self.assertIn("python-functions", data["completed_lessons"])
                self.assertEqual(data["mastery"]["functions"], 43)

    def test_exercise_catalog_lists_curriculum_practice(self) -> None:
        output = StringIO()
        with patch("ghost.modules.learning.PROGRESS_FILE", Path("/missing/learning.json")):
            exercises_report(Console(file=output))
        self.assertIn("Python coding exercises", output.getvalue())
        self.assertIn("greeting", output.getvalue())
        self.assertIn("project_plan", output.getvalue())

    def test_requested_hint_does_not_record_an_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("ghost.modules.learning.CONFIG_DIR", root), patch(
                "ghost.modules.learning.PROGRESS_FILE", root / "learning.json"
            ):
                output = StringIO()
                exercise_command(Console(file=output), "greeting", hint_number=2)
                self.assertIn("Use an f-string", output.getvalue())
                self.assertEqual(load_progress()["attempts"], {})


class ExerciseRunnerTests(unittest.TestCase):
    def test_foundation_lessons_use_complete_program_exercises(self) -> None:
        lessons = lessons_for()
        for lesson in lessons[:6]:
            with self.subTest(lesson=lesson.id):
                self.assertTrue(lesson.exercise_ids)
                self.assertTrue(all(EXERCISES[item].mode == "script" for item in lesson.exercise_ids))
        course_exercises = [exercise_id for lesson in lessons for exercise_id in lesson.exercise_ids]
        self.assertEqual(len(course_exercises), len(set(course_exercises)))
        linked = set(course_exercises)
        self.assertEqual(linked, set(EXERCISES))

    def test_python_lesson_examples_have_valid_syntax_and_all_examples_are_labelled(self) -> None:
        for lesson in lessons_for():
            self.assertEqual(len(lesson.examples), len(lesson.example_languages), lesson.id)
            for (heading, code), language in zip(lesson.examples, lesson.example_languages):
                with self.subTest(lesson=lesson.id, example=heading):
                    self.assertIn(language, {"python", "shell", "text"})
                    if language == "python":
                        compile(code, f"{lesson.id}:{heading}", "exec")

    def test_every_lesson_explains_each_example(self) -> None:
        for lesson in lessons_for():
            with self.subTest(lesson=lesson.id):
                self.assertEqual(len(lesson.examples), len(lesson.example_walkthroughs))
                self.assertEqual(len(lesson.examples), len(lesson.example_languages))
                self.assertTrue(all(item.strip() for item in lesson.example_walkthroughs))

    def test_object_oriented_and_context_lessons_demonstrate_core_syntax(self) -> None:
        lessons = {lesson.id: lesson for lesson in lessons_for()}
        class_examples = "\n".join(code for _, code in lessons["python-classes"].examples)
        context_examples = "\n".join(code for _, code in lessons["python-context"].examples)
        self.assertIn("class Dog(Animal)", class_examples)
        self.assertIn("self.items = items", class_examples)
        self.assertIn("@announce", context_examples)
        self.assertIn("def __enter__", context_examples)
        self.assertIn("def __exit__", context_examples)

    def test_lesson_examples_match_their_names_and_course_prerequisites(self) -> None:
        lessons = {lesson.id: lesson for lesson in lessons_for()}
        loop_lesson = lessons["python-loops"]
        self.assertIn("range(1, 4)", loop_lesson.example_walkthroughs[0])
        error_lesson = lessons["python-errors"]
        self.assertEqual(error_lesson.examples[1][0], "Handle a conversion error")
        classes = lessons["python-classes"]
        cart_example = next(code for title, code in classes.examples if title == "Compose behavior")
        self.assertIn("for item in self.items", cart_example)
        self.assertFalse(any(isinstance(node, ast.GeneratorExp) for node in ast.walk(ast.parse(cart_example))))
        tests_example = lessons["python-tests"].examples[0][1]
        self.assertLess(tests_example.index("def square"), tests_example.index("class TestSquare"))

    def test_every_course_exercise_has_a_solution_and_cases(self) -> None:
        for lesson in lessons_for():
            for exercise_id in lesson.exercise_ids:
                self.assertIn(exercise_id, EXERCISES)
                exercise = EXERCISES[exercise_id]
                self.assertTrue(exercise.tests)
                passed, message = run_exercise(exercise, exercise.solution)
                self.assertTrue(passed, f"{exercise_id}: {message}")

    def test_multiple_cases_pass(self) -> None:
        passed, message = run_exercise(EXERCISES["greeting"], EXERCISES["greeting"].solution)
        self.assertTrue(passed, message)
        self.assertIn("3 test cases", message)

    def test_script_exercise_supplies_stdin_and_checks_stdout(self) -> None:
        exercise = EXERCISES["interactive_greeting"]
        self.assertEqual(exercise.mode, "script")
        passed, message = run_exercise(exercise, exercise.solution)
        self.assertTrue(passed, message)
        failed, message = run_exercise(
            exercise,
            "name = input()\nprint(f'Hello, {name}!')\n",
        )
        self.assertFalse(failed)
        self.assertIn("Case 1", message)

    def test_script_exercise_uses_isolated_file_fixtures_and_checks_missing_files(self) -> None:
        exercise = EXERCISES["file_summary"]
        passed, message = run_exercise(exercise, exercise.solution)
        self.assertTrue(passed, message)
        self.assertIn("4 test cases", message)
        failed, message = run_exercise(
            exercise,
            "from pathlib import Path\n"
            "filename = input('File: ')\n"
            "print(f'{len(Path(filename).read_text().splitlines())} lines')\n",
        )
        self.assertFalse(failed)
        self.assertIn("FileNotFoundError", message)

    def test_http_exercise_uses_local_fixtures_and_checks_http_and_json_errors(self) -> None:
        exercise = EXERCISES["api_client"]
        self.assertEqual(exercise.mode, "http")
        passed, message = run_exercise(exercise, exercise.solution)
        self.assertTrue(passed, message)
        self.assertIn("3 test cases", message)
        failed, message = run_exercise(
            exercise,
            "import json\n"
            "from urllib.request import urlopen\n"
            "url = input('URL: ')\n"
            "with urlopen(url, timeout=2) as response:\n"
            "    print(json.load(response).get('name', 'Unknown'))\n",
        )
        self.assertFalse(failed)
        self.assertIn("Case 2", message)

    def test_input_output_lesson_uses_a_real_interactive_exercise(self) -> None:
        lesson = next(item for item in lessons_for() if item.id == "python-io")
        self.assertIn("interactive_greeting", lesson.exercise_ids)
        self.assertNotIn("2026", lesson.examples[0][1])

    def test_file_lesson_has_a_file_system_exercise(self) -> None:
        lesson = next(item for item in lessons_for() if item.id == "python-files")
        self.assertIn("file_summary", lesson.exercise_ids)

    def test_api_lesson_requires_a_real_http_exercise(self) -> None:
        lesson = next(item for item in lessons_for() if item.id == "python-json-api")
        self.assertIn("api_client", lesson.exercise_ids)

    def test_debug_output_does_not_turn_a_passing_submission_into_a_failure(self) -> None:
        source = "print('debug output')\n" + EXERCISES["greeting"].solution
        passed, message = run_exercise(EXERCISES["greeting"], source)
        self.assertTrue(passed, message)

    def test_wrong_result_reports_failed_case(self) -> None:
        passed, message = run_exercise(EXERCISES["greeting"], "def greet(name):\n    return name\n")
        self.assertFalse(passed)
        self.assertIn("Case 1", message)

    def test_timeout_is_reported(self) -> None:
        exercise = EXERCISES["greeting"]
        passed, message = run_exercise(exercise, "def greet(name):\n    while True: pass\n", timeout=0.2)
        self.assertFalse(passed)
        self.assertIn("Timed out", message)


if __name__ == "__main__":
    unittest.main()
