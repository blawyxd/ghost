from __future__ import annotations

import io
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rich.console import Console

from ghost.modules.maintenance import (
    backups_report, clean_cache, orphans_report, restore_backup,
    security_report, service_state, temp_report,
)


class MaintenanceTests(unittest.TestCase):
    def test_service_state_distinguishes_unknown_from_inactive(self) -> None:
        inactive = subprocess.CompletedProcess([], 3, "", "")
        with patch("ghost.modules.maintenance.run_command", return_value=inactive):
            self.assertIs(service_state("ufw"), False)
        with patch("ghost.modules.maintenance.run_command", return_value=None):
            self.assertIsNone(service_state("ufw"))

    def test_security_report_marks_unavailable_systemd_as_unknown(self) -> None:
        output = io.StringIO()
        with patch("ghost.modules.maintenance.service_state", return_value=None), patch(
            "ghost.modules.maintenance.run_command", return_value=None
        ), patch("ghost.modules.maintenance.shutil.which", return_value=None):
            security_report(Console(file=output))
        self.assertIn("Could not inspect systemd firewall units", output.getvalue())
        self.assertIn("Could not inspect the SSH service", output.getvalue())
        self.assertIn("UNKNOWN", output.getvalue())

    def _make_backup(self, backup_dir: Path, members: dict[str, bytes]) -> str:
        backup_dir.mkdir(parents=True, exist_ok=True)
        archive_path = backup_dir / "ghost-config-restore-test.tar.gz"
        with tarfile.open(archive_path, "w:gz") as archive:
            for name, content in members.items():
                info = tarfile.TarInfo(name)
                info.size = len(content)
                info.mode = 0o644
                archive.addfile(info, io.BytesIO(content))
        return archive_path.name

    def test_backup_restore_adds_missing_file_after_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backup_dir = root / "backups"
            archive_name = self._make_backup(
                backup_dir, {".config/ghost/settings.toml": b"theme='dark'\n"}
            )
            output = io.StringIO()
            with patch("ghost.modules.maintenance.BACKUP_DIR", backup_dir), patch(
                "ghost.modules.maintenance.Path.home", return_value=root
            ), patch("ghost.modules.maintenance.typer.confirm", return_value=True):
                restore_backup(Console(file=output), archive_name)
            restored = root / ".config" / "ghost" / "settings.toml"
            self.assertEqual(restored.read_bytes(), b"theme='dark'\n")
            self.assertIn("Restored 1 file", output.getvalue())

    def test_backup_restore_never_overwrites_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backup_dir = root / "backups"
            archive_name = self._make_backup(
                backup_dir, {".config/ghost/settings.toml": b"backup"}
            )
            target = root / ".config" / "ghost" / "settings.toml"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"current")
            output = io.StringIO()
            with patch("ghost.modules.maintenance.BACKUP_DIR", backup_dir), patch(
                "ghost.modules.maintenance.Path.home", return_value=root
            ), patch("ghost.modules.maintenance.typer.confirm", return_value=True):
                restore_backup(Console(file=output), archive_name)
            self.assertEqual(target.read_bytes(), b"current")
            self.assertIn("Skip · already exists", output.getvalue())

    def test_backup_restore_rejects_traversal_entries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backup_dir = root / "backups"
            archive_name = self._make_backup(
                backup_dir, {".config/../../outside.txt": b"unsafe"}
            )
            output = io.StringIO()
            with patch("ghost.modules.maintenance.BACKUP_DIR", backup_dir), patch(
                "ghost.modules.maintenance.Path.home", return_value=root
            ), patch("ghost.modules.maintenance.typer.confirm", return_value=True):
                restore_backup(Console(file=output), archive_name)
            self.assertFalse((root / "outside.txt").exists())
            self.assertIn("unsafe", output.getvalue())
            self.assertFalse((root / ".config").exists())

    def test_backup_restore_cancel_makes_no_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backup_dir = root / "backups"
            archive_name = self._make_backup(
                backup_dir, {".config/ghost/file.conf": b"value"}
            )
            output = io.StringIO()
            with patch("ghost.modules.maintenance.BACKUP_DIR", backup_dir), patch(
                "ghost.modules.maintenance.Path.home", return_value=root
            ), patch("ghost.modules.maintenance.typer.confirm", return_value=False):
                restore_backup(Console(file=output), archive_name)
            self.assertFalse((root / ".config").exists())
            self.assertIn("Restore cancelled", output.getvalue())

    def test_cache_preview_is_exact_and_cancel_preserves_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "cache"
            (root / "browser").mkdir(parents=True)
            (root / "browser" / "index.bin").write_bytes(b"cache-data")
            output = io.StringIO()
            with patch("ghost.modules.maintenance.CACHE_DIR", root), patch(
                "ghost.modules.maintenance.typer.confirm", return_value=False
            ):
                clean_cache(Console(file=output))
            self.assertIn(str(root / "browser"), output.getvalue())
            self.assertIn("Directory (recursive)", output.getvalue())
            self.assertTrue((root / "browser" / "index.bin").exists())

    def test_cache_cleanup_refuses_when_inventory_is_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "cache"
            root.mkdir()
            output = io.StringIO()
            with patch("ghost.modules.maintenance.CACHE_DIR", root), patch(
                "ghost.modules.maintenance._cache_inventory", return_value=None
            ), patch("ghost.modules.maintenance.typer.confirm") as confirm:
                clean_cache(Console(file=output))
            confirm.assert_not_called()
            self.assertIn("cleanup was not started", output.getvalue())

    def test_confirmed_cache_cleanup_only_removes_previewed_children(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "cache"
            root.mkdir()
            (root / "entry.tmp").write_text("temporary", encoding="utf-8")
            protected = Path(directory) / "keep.txt"
            protected.write_text("keep", encoding="utf-8")
            with patch("ghost.modules.maintenance.CACHE_DIR", root), patch(
                "ghost.modules.maintenance.typer.confirm", return_value=True
            ):
                clean_cache(Console(file=io.StringIO()))
            self.assertFalse((root / "entry.tmp").exists())
            self.assertTrue(protected.exists())

    def test_backup_inventory_checks_archive_readability(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive_path = root / "ghost-config-test.tar.gz"
            with tarfile.open(archive_path, "w:gz") as archive:
                info = tarfile.TarInfo(".config/example.conf")
                info.size = 4
                import io as binary_io
                archive.addfile(info, binary_io.BytesIO(b"test"))
            output = io.StringIO()
            with patch("ghost.modules.maintenance.BACKUP_DIR", root):
                backups_report(Console(file=output))
            self.assertIn("ghost-config-test.tar.gz", output.getvalue())
            self.assertIn("Yes", output.getvalue())

    def test_backup_inventory_reads_payload_and_detects_compression_corruption(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive_path = root / "ghost-config-damaged.tar.gz"
            with tarfile.open(archive_path, "w:gz") as archive:
                info = tarfile.TarInfo(".config/example.conf")
                info.size = 8
                archive.addfile(info, io.BytesIO(b"contents"))
            corrupted = bytearray(archive_path.read_bytes())
            corrupted[-8] ^= 0xFF  # Corrupt the gzip CRC; headers remain readable.
            archive_path.write_bytes(corrupted)
            output = io.StringIO()
            with patch("ghost.modules.maintenance.BACKUP_DIR", root):
                backups_report(Console(file=output))
            report = output.getvalue()
            self.assertIn("ghost-config-damaged.tar.gz", report)
            self.assertIn("No", report)

    def test_orphan_inspection_handles_unavailable_package_manager(self) -> None:
        output = io.StringIO()
        with patch("ghost.modules.maintenance.shutil.which", return_value=None):
            orphans_report(Console(file=output))
        self.assertIn("unavailable", output.getvalue())

    def test_temp_report_is_read_only_and_uses_configured_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sample.tmp").write_text("temporary", encoding="utf-8")
            output = io.StringIO()
            with patch("ghost.modules.maintenance.TEMP_DIRS", (root,)):
                temp_report(Console(file=output))
            self.assertIn("sample.tmp", output.getvalue())
            self.assertTrue((root / "sample.tmp").exists())

    def test_temp_report_does_not_report_empty_when_location_is_unavailable(self) -> None:
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing"
            with patch("ghost.modules.maintenance.TEMP_DIRS", (missing,)):
                temp_report(Console(file=output))
        report = output.getvalue()
        self.assertIn("could not be inspected", report)
        self.assertNotIn("No entries found", report)


if __name__ == "__main__":
    unittest.main()
