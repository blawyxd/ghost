from __future__ import annotations

import sys
import unittest

from ghost.modules.diagnostics import run_command


class DiagnosticCommandTests(unittest.TestCase):
    def test_nonzero_exit_is_not_an_empty_success(self) -> None:
        output, error = run_command([
            sys.executable, "-c", "print('partial'); raise SystemExit(7)"
        ])
        self.assertEqual(output, "")
        self.assertIn("status 7", error)

    def test_missing_command_is_reported(self) -> None:
        output, error = run_command(["ghost-command-that-does-not-exist"])
        self.assertEqual(output, "")
        self.assertTrue(error)


if __name__ == "__main__":
    unittest.main()
