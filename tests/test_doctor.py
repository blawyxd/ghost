from __future__ import annotations

import io
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from rich.console import Console

from ghost.modules.doctor import doctor_report, parse_memory_usage


class DoctorReportTests(unittest.TestCase):
    def test_memory_parser_requires_total_and_available_values(self) -> None:
        self.assertIsNone(parse_memory_usage("MemTotal: 1000 kB\n"))
        self.assertIsNone(parse_memory_usage("MemTotal: 1000 kB\nMemAvailable: 1200 kB\n"))
        self.assertEqual(
            parse_memory_usage("MemTotal: 1000 kB\nMemAvailable: 250 kB\n"),
            (750, 1000, 75.0),
        )

    def test_unavailable_identity_and_memory_data_are_not_reported_as_healthy(self) -> None:
        output = io.StringIO()
        with (
            patch("ghost.modules.doctor.Path.exists", return_value=False),
            patch("ghost.modules.doctor.run_command", return_value=None),
            patch("ghost.modules.doctor.shutil.which", return_value=None),
            patch(
                "ghost.modules.doctor.shutil.disk_usage",
                return_value=SimpleNamespace(total=100, used=20, free=80),
            ),
        ):
            doctor_report(Console(file=output, width=120))

        report = output.getvalue()
        self.assertIn("Distribution", report)
        self.assertIn("CPU", report)
        self.assertIn("Memory", report)
        self.assertIn("Could not read memory totals", report)
        self.assertIn("unknown or unavailable", report)
        self.assertNotIn("CPU                   Unknown                     OK", report)


if __name__ == "__main__":
    unittest.main()
