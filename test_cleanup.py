#!/usr/bin/env python3
"""Offline retention/failure tests using synthetic temporary files and mocks."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

_IMPORT_LOGS = tempfile.TemporaryDirectory(prefix="backup-cleanup-test-logs-")
with patch.dict(os.environ, {"LOG_DIR": _IMPORT_LOGS.name}):
    import backup


class BackupLifecycleTests(unittest.TestCase):
    def configuration(self, folder):
        return {
            "DB_HOST": "db.example", "DB_USER": "backup", "DB_PASSWORD": "synthetic-fixture",
            "DB_NAME": "synthetic", "GOOGLE_DRIVE_FOLDER_ID": "synthetic-folder",
            "SERVICE_ACCOUNT_FILE": "/nonexistent-synthetic-service-account.json",
            "DOCUMENTS_PATH": str(folder / "documents"), "BACKUP_DIR": str(folder),
            "BACKUP_RETENTION_COUNT": "7",
        }

    def prepare(self, folder):
        db = folder / "synthetic.sql"
        db.write_text("-- synthetic SQL")
        docs = folder / "synthetic-documents"
        docs.mkdir()
        (docs / "example.txt").write_text("synthetic document")
        unrelated = folder / "unrelated.txt"
        unrelated.write_text("preserve unrelated data")
        return db, docs, unrelated

    def run_backup(self, folder, db, docs, upload_result):
        with patch.dict(os.environ, self.configuration(folder), clear=True):
            with patch("dotenv.load_dotenv", return_value=False) as load_env, \
                    patch.object(backup, "debug_environment"), \
                    patch.object(backup, "GoogleDriveService") as service, \
                    patch.object(backup, "backup_database", return_value=str(db) if db else None), \
                    patch.object(backup, "backup_documents", return_value=str(docs) if docs else None), \
                    patch.object(backup, "cleanup_backup_directory") as broad_cleanup:
                drive = service.return_value
                drive.check_folder_access.return_value = True
                drive.upload_file.return_value = upload_result
                if upload_result and db and docs:
                    backup.main()
                else:
                    with self.assertRaises(SystemExit) as exit_error:
                        backup.main()
                    self.assertEqual(exit_error.exception.code, 1)
                load_env.assert_called_once_with()
                broad_cleanup.assert_not_called()
                return drive

    def test_failed_upload_keeps_recoverable_backup_and_other_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            db, docs, unrelated = self.prepare(folder)
            drive = self.run_backup(folder, db, docs, None)
            self.assertTrue(db.is_file())
            self.assertTrue(docs.is_dir())
            self.assertTrue(unrelated.is_file())
            self.assertEqual(len(list(folder.glob("dolibarr_backup_*.tar.gz"))), 1)
            drive.upload_file.assert_called_once()
            drive.delete_old_backups.assert_not_called()

    def test_missing_component_never_uploads_or_prunes_remote_backups(self):
        for missing in ("database", "documents"):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as temporary:
                folder = Path(temporary)
                db, docs, unrelated = self.prepare(folder)
                drive = self.run_backup(folder, None if missing == "database" else db,
                                        None if missing == "documents" else docs, None)
                drive.upload_file.assert_not_called()
                drive.delete_old_backups.assert_not_called()
                self.assertTrue(db.is_file())
                self.assertTrue(docs.is_dir())
                self.assertTrue(unrelated.is_file())
                self.assertEqual(list(folder.glob("dolibarr_backup_*.tar.gz")), [])

    def test_success_only_cleans_the_current_uploaded_attempt(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            db, docs, unrelated = self.prepare(folder)
            older = folder / "dolibarr_backup_previous.tar.gz"
            older.write_text("synthetic retained backup")
            drive = self.run_backup(folder, db, docs, "synthetic-upload-id")
            drive.delete_old_backups.assert_called_once_with("synthetic-folder", keep_count=7)
            self.assertFalse(db.exists())
            self.assertFalse(docs.exists())
            self.assertTrue(unrelated.is_file())
            self.assertTrue(older.is_file())

    def test_cleanup_files_changes_only_explicit_synthetic_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            db, docs, unrelated = self.prepare(folder)
            backup.cleanup_files(str(db), str(docs))
            self.assertFalse(db.exists())
            self.assertFalse(docs.exists())
            self.assertTrue(unrelated.is_file())

    def test_archive_requires_both_existing_backup_components(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            db, docs, unrelated = self.prepare(folder)
            self.assertEqual(backup.create_archive(str(db), str(folder / "missing"), "synthetic", str(folder)), (None, None))
            self.assertEqual(backup.create_archive(None, str(docs), "synthetic", str(folder)), (None, None))
            self.assertEqual(list(folder.glob("*.tar.gz")), [])
            self.assertTrue(db.is_file())
            self.assertTrue(docs.is_dir())
            self.assertTrue(unrelated.is_file())


if __name__ == "__main__":
    unittest.main()
