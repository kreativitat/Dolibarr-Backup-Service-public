#!/usr/bin/env python3
"""Offline security regressions; no database or Google Drive access is used."""
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import unittest
from unittest.mock import patch

_IMPORT_LOGS = tempfile.TemporaryDirectory(prefix="backup-test-logs-")
with patch.dict(os.environ, {"LOG_DIR": _IMPORT_LOGS.name}):
    import backup


class DatabaseSecurityTests(unittest.TestCase):
    def test_password_is_child_environment_only_and_sql_is_not_logged(self):
        password = secrets.token_hex(16) + ";$(echo synthetic)"
        sql = "-- synthetic private SQL payload\n"
        calls = []

        def run(args, **kwargs):
            calls.append((args, kwargs))
            self.assertIsInstance(args, list)
            self.assertNotIn(password, " ".join(args))
            self.assertFalse(kwargs.get("shell", False))
            self.assertEqual(kwargs["env"]["MYSQL_PWD"], password)
            self.assertNotIn("--skip-ssl", args)
            if args[0] == "mariadb-dump":
                kwargs["stdout"].write(sql)
                return subprocess.CompletedProcess(args, 0)
            return subprocess.CompletedProcess(args, 0, stdout="1\n")

        old_password = os.environ.get("MYSQL_PWD")
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(backup.subprocess, "run", side_effect=run):
                with self.assertLogs("dolibarr_backup", level="INFO") as logs:
                    path = backup.backup_database("db.example", "backup", password, "synthetic", folder)
            self.assertIsNotNone(path)
            self.assertEqual(Path(path).read_text(), sql)
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
        self.assertEqual(len(calls), 2)
        self.assertEqual(os.environ.get("MYSQL_PWD"), old_password)
        captured = "\n".join(logs.output)
        self.assertNotIn(password, captured)
        self.assertNotIn(sql.strip(), captured)

    def test_subprocess_failure_does_not_log_command_or_payloads(self):
        password = secrets.token_hex(16)
        payload = "synthetic confidential result"
        error = subprocess.CalledProcessError(2, ["mysql", password], output=payload, stderr=password)
        with patch.object(backup.subprocess, "run", side_effect=error):
            with self.assertLogs("dolibarr_backup", level="ERROR") as logs:
                self.assertIsNone(backup.run_command(["mysql", "--execute=SELECT 1;"], env={"MYSQL_PWD": password}))
        captured = "\n".join(logs.output)
        self.assertNotIn(password, captured)
        self.assertNotIn(payload, captured)
        self.assertIn("exit code 2", captured)

    def test_dump_failure_keeps_partial_file_without_logging_output(self):
        password = secrets.token_hex(16)
        payload = "synthetic partial SQL"

        def run(args, **kwargs):
            if args[0] == "mariadb-dump":
                kwargs["stdout"].write(payload)
                raise subprocess.CalledProcessError(2, args, output=payload, stderr=password)
            return subprocess.CompletedProcess(args, 0, stdout="1\n")

        with tempfile.TemporaryDirectory() as folder:
            with patch.object(backup.subprocess, "run", side_effect=run):
                with self.assertLogs("dolibarr_backup", level="ERROR") as logs:
                    self.assertIsNone(backup.backup_database("db.example", "backup", password, "synthetic", folder))
            files = list(Path(folder).glob("*.sql"))
            self.assertEqual(len(files), 1)
            self.assertEqual(files[0].read_text(), payload)
        self.assertNotIn(password, "\n".join(logs.output))
        self.assertNotIn(payload, "\n".join(logs.output))

    def test_document_paths_are_copied_without_a_shell(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "documents;$(echo synthetic)"
            source.mkdir()
            (source / "example.txt").write_text("synthetic document")
            destination = Path(folder) / "backup path"
            with patch.object(backup.subprocess, "run") as run:
                result = backup.backup_documents("synthetic", str(source), str(destination))
            run.assert_not_called()
            self.assertEqual((Path(result) / "example.txt").read_text(), "synthetic document")


if __name__ == "__main__":
    unittest.main()
