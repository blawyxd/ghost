from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rich.console import Console

from ghost.modules.learning import load_progress
from ghost.modules.learning.curriculum import lessons_for
from ghost.modules.learning.projects import PROJECTS, projects_report
from ghost.modules.learning.project_review import inspect_project


class LearningProjectTests(unittest.TestCase):
    def test_read_only_review_checks_source_tests_and_syntax_without_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / "executed.txt"
            (root / "app.py").write_text(
                "from pathlib import Path\nPath('executed.txt').write_text('ran')\n", encoding="utf-8"
            )
            (root / "tests").mkdir()
            (root / "tests" / "test_app.py").write_text("def test_example():\n    assert True\n", encoding="utf-8")
            (root / "README.md").write_text("Example project\n", encoding="utf-8")
            checks = inspect_project(next(item for item in PROJECTS if item.id == "todo-cli"), root)
            self.assertTrue(all(check.status != "FAIL" for check in checks), checks)
            self.assertFalse(marker.exists())

    def test_review_reports_syntax_errors_and_missing_package_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text("def broken(:\n", encoding="utf-8")
            (root / "test_app.py").write_text("def test_example():\n    pass\n", encoding="utf-8")
            checks = inspect_project(next(item for item in PROJECTS if item.id == "modular-service"), root)
            by_name = {check.name: check for check in checks}
            self.assertEqual(by_name["Python syntax"].status, "FAIL")
            self.assertEqual(by_name["Build metadata"].status, "FAIL")

    def test_project_review_command_does_not_change_milestone_progress(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project_dir = root / "project"
            project_dir.mkdir()
            (project_dir / "app.py").write_text("def main():\n    return 0\n", encoding="utf-8")
            (project_dir / "test_app.py").write_text("def test_main():\n    assert True\n", encoding="utf-8")
            output = io.StringIO()
            with patch("ghost.modules.learning.CONFIG_DIR", root / "config"), patch(
                "ghost.modules.learning.PROGRESS_FILE", root / "config" / "learning.json"
            ):
                projects_report(Console(file=output), "todo-cli", review_path=project_dir)
                self.assertFalse((root / "config" / "learning.json").exists())
            self.assertIn("Structural checks passed", output.getvalue())

    def test_projects_reference_existing_lessons_and_have_acceptance_checks(self) -> None:
        lesson_ids = {lesson.id for lesson in lessons_for()}
        self.assertGreaterEqual(len(PROJECTS), 8)
        for project in PROJECTS:
            self.assertTrue(project.milestones, project.id)
            self.assertTrue(project.acceptance, project.id)
            self.assertTrue(set(project.lessons).issubset(lesson_ids), project.id)
        organiser = next(project for project in PROJECTS if project.id == "file-organiser")
        self.assertTrue(any("Default execution changes no files" in line for line in organiser.acceptance))

    def test_milestone_progress_persists_without_gamification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = io.StringIO()
            with patch("ghost.modules.learning.CONFIG_DIR", root), patch(
                "ghost.modules.learning.PROGRESS_FILE", root / "learning.json"
            ):
                projects_report(Console(file=output), "todo-cli", 1)
                progress = load_progress()
            self.assertEqual(progress["project_progress"]["todo-cli"]["completed_milestones"], [1])
            self.assertFalse(progress["project_progress"]["todo-cli"]["completed"])
            self.assertEqual(progress["xp"], 0)
            self.assertIn("Milestone 1 marked complete", output.getvalue())

    def test_invalid_milestone_does_not_persist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = io.StringIO()
            with patch("ghost.modules.learning.CONFIG_DIR", root), patch(
                "ghost.modules.learning.PROGRESS_FILE", root / "learning.json"
            ):
                projects_report(Console(file=output), "calculator", 999)
                self.assertFalse((root / "learning.json").exists())
            self.assertIn("Milestone must be between", output.getvalue())

    def test_project_milestones_must_be_completed_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = io.StringIO()
            with patch("ghost.modules.learning.CONFIG_DIR", root), patch(
                "ghost.modules.learning.PROGRESS_FILE", root / "learning.json"
            ):
                projects_report(Console(file=output), "todo-cli", 2)
                self.assertFalse((root / "learning.json").exists())
            self.assertIn("Complete milestone 1 first", output.getvalue())

    def test_project_list_ignores_duplicate_and_invalid_milestone_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = io.StringIO()
            with patch("ghost.modules.learning.CONFIG_DIR", root), patch(
                "ghost.modules.learning.PROGRESS_FILE", root / "learning.json"
            ):
                from ghost.modules.learning import save_progress

                save_progress({
                    "project_progress": {
                        "todo-cli": {"completed_milestones": [1, 1, 999, -1, True]}
                    }
                })
                projects_report(Console(file=output))
            self.assertIn("20%", output.getvalue())


if __name__ == "__main__":
    unittest.main()
