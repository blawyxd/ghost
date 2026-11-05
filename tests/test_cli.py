from __future__ import annotations

import io
import unittest
from unittest.mock import patch

from rich.console import Console

import main


class CliHelpTests(unittest.TestCase):
    def test_help_catalog_covers_every_registered_command(self) -> None:
        entries = main.command_catalog()
        expected = {
            info.name or info.callback.__name__.replace("_", "-")
            for info in main.app.registered_commands
            if info.callback is not None
        }
        self.assertEqual({name for name, _ in entries}, expected)
        self.assertTrue(all(description.strip() for _, description in entries))

    def test_help_command_renders_registered_commands(self) -> None:
        output = io.StringIO()
        with patch.object(main, "console", Console(file=output, width=160)):
            main.show_help()
        rendered = output.getvalue()
        for name, _ in main.command_catalog():
            self.assertIn(f"ghost {name}", rendered)
        self.assertIn("ghost updates", rendered)
        self.assertIn("ghost disk", rendered)
        self.assertIn("ghost large", rendered)


if __name__ == "__main__":
    unittest.main()
