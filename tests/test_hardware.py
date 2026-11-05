from __future__ import annotations

import unittest
from unittest.mock import patch

from ghost.modules.hardware import get_cpu_info, get_gpu_info, get_memory_info, get_storage_info


class HardwareInfoTests(unittest.TestCase):
    def test_gpu_inventory_distinguishes_unavailable_tools_from_empty_inventory(self) -> None:
        with patch("ghost.modules.hardware.run_command", return_value=None):
            self.assertIsNone(get_gpu_info())
        with patch("ghost.modules.hardware.run_command", side_effect=[None, ""]):
            self.assertEqual(get_gpu_info(), [])

    def test_storage_inventory_distinguishes_unavailable_tool_from_no_drives(self) -> None:
        with patch("ghost.modules.hardware.run_command", return_value=None):
            self.assertIsNone(get_storage_info())
        with patch(
            "ghost.modules.hardware.run_command",
            return_value='{"blockdevices": []}',
        ):
            self.assertEqual(get_storage_info(), [])

    def test_storage_inventory_rejects_invalid_command_output(self) -> None:
        with patch("ghost.modules.hardware.run_command", return_value="not json"):
            self.assertIsNone(get_storage_info())

    def test_cpu_core_count_is_unknown_when_proc_does_not_expose_core_ids(self) -> None:
        with patch(
            "ghost.modules.hardware.read_file",
            side_effect=["model name: Example CPU", ""],
        ), patch("ghost.modules.hardware.os.cpu_count", return_value=8):
            info = get_cpu_info()
        self.assertEqual(info["cores"], "Unknown")
        self.assertEqual(info["threads"], "8")

    def test_memory_detail_does_not_assume_missing_available_memory_is_zero(self) -> None:
        with patch(
            "ghost.modules.hardware.read_file",
            return_value="MemTotal: 1048576 kB",
        ):
            info = get_memory_info()
        self.assertEqual(info, {"total": "Unknown", "used": "Unknown", "available": "Unknown"})

    def test_memory_detail_calculates_usage_when_both_values_exist(self) -> None:
        with patch(
            "ghost.modules.hardware.read_file",
            return_value="MemTotal: 1048576 kB\nMemAvailable: 524288 kB",
        ):
            info = get_memory_info()
        self.assertEqual(info["total"], "1.00 GB")
        self.assertEqual(info["used"], "0.50 GB")


if __name__ == "__main__":
    unittest.main()
