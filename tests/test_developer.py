from __future__ import annotations

import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rich.console import Console

import ghost.modules.developer.workflows as workflows
from ghost.modules.developer.workflows import (
    build_project,
    declared_python_dependencies,
    environment_report,
    find_project_root,
    install_dependencies,
    project_report,
    serve_project,
    server_command,
    test_project as run_project_tests,
)


class DeveloperWorkflowTests(unittest.TestCase):
    def test_node_build_requires_a_declared_build_script(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "package.json").write_text('{"scripts": {"dev": "vite"}}', encoding="utf-8")
            output = io.StringIO()
            with patch("ghost.modules.developer.workflows.find_project_root", return_value=root), patch(
                "ghost.modules.developer.workflows.shutil.which", return_value="/usr/bin/npm"
            ), patch("ghost.modules.developer.workflows._run_project_command") as run:
                build_project(Console(file=output), root)
            run.assert_not_called()
            self.assertIn("no 'build' script", output.getvalue())
            self.assertNotIn("completed successfully", output.getvalue())

    def test_node_build_runs_the_declared_build_script(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "package.json").write_text('{"scripts": {"build": "vite build"}}', encoding="utf-8")
            with patch("ghost.modules.developer.workflows.find_project_root", return_value=root), patch(
                "ghost.modules.developer.workflows.shutil.which", return_value="/usr/bin/npm"
            ), patch("ghost.modules.developer.workflows._run_project_command") as run:
                build_project(Console(file=io.StringIO()), root)
            self.assertEqual(run.call_args.args[2], ["npm", "run", "build"])

    def test_project_detection_walks_up_and_lists_types(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nested = root / "src" / "package"
            nested.mkdir(parents=True)
            (root / "pyproject.toml").write_text(
                '[project]\nname = "sample"\ndependencies = ["rich>=13"]\n',
                encoding="utf-8",
            )
            (nested / "module.py").write_text("value = 1\n", encoding="utf-8")
            (root / ".aws").mkdir()
            self.assertEqual(find_project_root(nested), root)
            output = io.StringIO()
            project_report(Console(file=output), nested)
            self.assertIn("Python", output.getvalue())
            self.assertIn("module.py", output.getvalue())
            self.assertNotIn(".aws", output.getvalue())

    def test_dependency_reader_combines_python_manifests(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pyproject.toml").write_text(
                '[project]\nname = "sample"\ndependencies = ["rich>=13"]\n'
                '[project.optional-dependencies]\ntest = ["pytest"]\n',
                encoding="utf-8",
            )
            (root / "requirements.txt").write_text("typer>=0.12\n# comment\n", encoding="utf-8")
            self.assertEqual(
                declared_python_dependencies(root),
                ["rich>=13", "pytest [test]", "typer>=0.12"],
            )

    def test_project_python_prefers_existing_virtual_environment(self) -> None:
        from ghost.modules.developer.workflows import project_python

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary_dir = root / ".venv" / "bin"
            binary_dir.mkdir(parents=True)
            python = binary_dir / "python"
            python.symlink_to(os.sys.executable)
            self.assertEqual(project_python(root), str(python))

    def test_project_report_does_not_attribute_an_unrelated_active_environment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pyproject.toml").write_text('[project]\nname="sample"\n', encoding="utf-8")
            local_environment = root / ".venv"
            local_environment.mkdir()
            output = io.StringIO()
            with patch("ghost.modules.developer.workflows.find_project_root", return_value=root), patch.object(
                workflows.sys, "prefix", "/tmp/unrelated-venv"
            ), patch.object(workflows.sys, "base_prefix", "/usr"):
                project_report(Console(file=output), root)
            self.assertIn("Found, not active", output.getvalue())
            self.assertNotIn("Active: /tmp/unrelated-venv", output.getvalue())

    def test_dependency_installation_defaults_to_cancel(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "requirements.txt").write_text("rich\n", encoding="utf-8")
            output = io.StringIO()
            with patch("ghost.modules.developer.workflows.find_project_root", return_value=root), patch(
                "ghost.modules.developer.workflows.typer.confirm", return_value=False
            ), patch("ghost.modules.developer.workflows._run_project_command") as run:
                install_dependencies(Console(file=output), root)
            run.assert_not_called()
            self.assertIn("pip install", output.getvalue())
            self.assertIn("cancelled", output.getvalue())

    def test_env_check_never_displays_values(self) -> None:
        output = io.StringIO()
        with patch.dict(os.environ, {"API_KEY": "top-secret-test-value"}):
            environment_report(Console(file=output))
        self.assertIn("API_KEY", output.getvalue())
        self.assertIn("Set", output.getvalue())
        self.assertNotIn("top-secret-test-value", output.getvalue())

    def test_test_helper_runs_detected_unittest_suite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tests = root / "tests"
            tests.mkdir()
            (tests / "test_sample.py").write_text(
                "import unittest\nclass Sample(unittest.TestCase):\n"
                "    def test_ok(self): self.assertEqual(2 + 2, 4)\n",
                encoding="utf-8",
            )
            output = io.StringIO()
            with patch("ghost.modules.developer.workflows.find_project_root", return_value=root), patch(
                "ghost.modules.developer.workflows.shutil.which", return_value=None
            ):
                run_project_tests(Console(file=output), root)
            self.assertIn("Tests completed successfully", output.getvalue())

    def test_static_server_defaults_to_loopback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "index.html").write_text("<h1>local</h1>", encoding="utf-8")
            command, label = server_command(root, port=8123)
            self.assertEqual(command[-5:], ["-m", "http.server", "8123", "--bind", "127.0.0.1"])
            self.assertIn("static", label)

    def test_npm_server_requires_declared_script(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "package.json").write_text(
                '{"scripts": {"dev": "vite"}}', encoding="utf-8"
            )
            with patch("ghost.modules.developer.workflows.shutil.which", return_value="/usr/bin/npm"):
                command, label = server_command(root, port=8123)
            self.assertEqual(command, ["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", "8123"])
            self.assertIn("npm script", label)

    def test_server_validates_host_and_port(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            command, message = server_command(root, host="localhost")
            self.assertIsNone(command)
            self.assertIn("IPv4", message)
            command, message = server_command(root, port=70000)
            self.assertIsNone(command)
            self.assertIn("Port", message)

    def test_server_starts_known_command_in_project_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "index.html").write_text("ok", encoding="utf-8")
            output = io.StringIO()
            with patch("ghost.modules.developer.workflows.find_project_root", return_value=root), patch(
                "ghost.modules.developer.workflows.subprocess.run", return_value=type("Result", (), {"returncode": 0})()
            ) as run:
                serve_project(Console(file=output), root, port=8123)
            self.assertEqual(run.call_args.kwargs["cwd"], root)
            self.assertIn("127.0.0.1:8123", output.getvalue())


if __name__ == "__main__":
    unittest.main()
