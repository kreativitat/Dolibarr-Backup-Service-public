#!/usr/bin/env python3
import os
import subprocess
import tarfile
import datetime
import sys
import logging
import shutil
import time
import shlex
from typing import Optional, List, Dict, Tuple, Union
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

# Try to import custom logging config, fallback to basic config
try:
    from logging_config import setup_logging
    # Use logs directory in current working directory if not specified
    log_dir = os.getenv('LOG_DIR', os.path.join(os.getcwd(), 'logs'))
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'backup.log')
    logger = setup_logging(
        log_file=log_file,
        log_level=os.getenv('LOG_LEVEL', 'INFO')
    )
    logging = logger  # Use configured logger
except ImportError:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)

class GoogleDriveService:
    """Encapsulates Google Drive authentication and common Drive API operations."""

    def __init__(self, service_account_file: str, scopes: List[str]) -> None:
        try:
            credentials = service_account.Credentials.from_service_account_file(
                service_account_file, scopes=scopes)
            self.drive_service = build('drive', 'v3', credentials=credentials)
            logging.info("Google Drive client initialized successfully.")
        except Exception as e:
            logging.error("Failed to initialize Google Drive client: %s", e)
            sys.exit(1)

    def check_folder_access(self, folder_id: str) -> bool:
        """Verify that a folder with the given ID exists and is accessible."""
        try:
            folder = self.drive_service.files().get(fileId=folder_id, fields="id, name").execute()
            logging.info("Folder found: %s (ID: %s)", folder.get("name"), folder.get("id"))
            return True
        except HttpError as e:
            logging.error("Error retrieving folder with ID %s: %s", folder_id, e)
            return False

    def upload_file(self, local_path: str, file_name: str, folder_id: str,
                   mime_type: str = 'application/gzip', max_retries: int = 3) -> Optional[str]:
        """Upload a file to Google Drive with retry logic."""
        for attempt in range(1, max_retries + 1):
            try:
                file_metadata = {'name': file_name, 'parents': [folder_id]}
                media = MediaFileUpload(local_path, mimetype=mime_type, resumable=True)
                file = self.drive_service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id'
                ).execute()
                logging.info("Uploaded file %s, new ID: %s", file_name, file.get('id'))
                return file.get('id')
            except HttpError as e:
                if attempt < max_retries:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logging.warning("Upload attempt %d failed for %s: %s. Retrying in %d seconds...",
                                  attempt, file_name, e, wait_time)
                    time.sleep(wait_time)
                else:
                    logging.error("Upload failed for file %s after %d attempts: %s",
                                file_name, max_retries, e)
                    return None
        return None

    def list_backup_files(self, folder_id: str) -> List[Dict]:
        """List backup files in the specified Google Drive folder."""
        try:
            query = f"'{folder_id}' in parents and name contains 'dolibarr_backup_' and trashed = false"
            response = self.drive_service.files().list(
                q=query,
                orderBy='createdTime desc',
                fields='files(id, name, createdTime)'
            ).execute()
            files = response.get('files', [])
            logging.info("Found %d backup files in folder", len(files))
            return files
        except HttpError as e:
            logging.error("Failed to list backup files: %s", e)
            return []

    def delete_old_backups(self, folder_id: str, keep_count: int = 7) -> None:
        """Delete old backup files, keeping only the specified number of latest backups."""
        try:
            backup_files = self.list_backup_files(folder_id)

            if len(backup_files) <= keep_count:
                logging.info("No old backups to delete (%d files, keeping %d)", len(backup_files), keep_count)
                return

            files_to_delete = backup_files[keep_count:]
            logging.info("Deleting %d old backup files", len(files_to_delete))

            for file in files_to_delete:
                try:
                    self.drive_service.files().delete(fileId=file['id']).execute()
                    logging.info("Deleted old backup: %s", file['name'])
                except HttpError as e:
                    logging.error("Failed to delete backup %s: %s", file['name'], e)

        except Exception as e:
            logging.error("Error in delete_old_backups: %s", e)

def run_command(command: Union[str, List[str]], env: Optional[Dict[str, str]] = None) -> Optional[str]:
    """Run an argument list without logging arguments or process payloads."""
    args = shlex.split(command) if isinstance(command, str) else command
    try:
        result = subprocess.run(args, env=env, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logging.error("Command failed with exit code %s", e.returncode)
        return None
    except OSError as e:
        logging.error("Cannot start command (%s)", type(e).__name__)
        return None

def _database_environment(password: str) -> Dict[str, str]:
    """Pass the password only to the client process, never through its argv."""
    env = os.environ.copy()
    env['MYSQL_PWD'] = password
    return env

def backup_database(db_host: str, db_user: str, db_password: str, db_name: str, backup_dir: str = "./backups") -> Optional[str]:
    """Backup the Dolibarr database using mariadb-dump."""
    logging.info("Starting database backup...")

    # Create backup directory if it doesn't exist
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    db_backup_file = os.path.join(backup_dir, f"dolibarr_db_{timestamp}.sql")

    # Test database connection first
    db_env = _database_environment(db_password)
    test_command = ['mysql', '--host=' + db_host, '--user=' + db_user, '--execute=SELECT 1;']
    logging.info("Testing database connection...")
    if not run_command(test_command, env=db_env):
        logging.error("Cannot connect to database")
        return None

    # Database backup command
    db_command = ['mariadb-dump', '--host=' + db_host, '--user=' + db_user, '--', db_name]

    try:
        logging.info("Running database backup command...")
        # Keep SQL out of memory/logs and create private files without overwriting
        # a previous attempt that used the same timestamp.
        fd = os.open(db_backup_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            subprocess.run(db_command, env=db_env, stdout=f, stderr=subprocess.PIPE,
                           text=True, check=True)

        # Check if file has content
        if os.path.getsize(db_backup_file) > 0:
            logging.info("Database backup completed: %s (%d bytes)", db_backup_file, os.path.getsize(db_backup_file))
            return db_backup_file
        else:
            logging.error("Database backup file is empty")
            return None

    except subprocess.CalledProcessError as e:
        logging.error("Database backup command failed with exit code %s", e.returncode)
        return None
    except OSError as e:
        logging.error("Cannot create database backup (%s)", type(e).__name__)
        return None

def backup_documents(timestamp: str, documents_path: str, backup_dir: str = "./backups") -> Optional[str]:
    """Copy documents directory for backup."""
    logging.info("Starting documents backup...")

    # Create backup directory if it doesn't exist
    os.makedirs(backup_dir, exist_ok=True)

    docs_backup_dir = os.path.join(backup_dir, f"dolibarr_documents_{timestamp}")

    # Check if documents directory exists
    if not os.path.isdir(documents_path):
        logging.error("Documents directory %s does not exist", documents_path)
        return None

    # Check contents of documents directory
    try:
        doc_contents = os.listdir(documents_path)
        logging.info("Documents directory contains %d items", len(doc_contents))
    except Exception as e:
        logging.error("Cannot read documents directory: %s", e)
        return None

    try:
        shutil.copytree(documents_path, docs_backup_dir)

        # Verify the copy worked
        if os.path.exists(docs_backup_dir) and os.listdir(docs_backup_dir):
            copied_items = len(os.listdir(docs_backup_dir))
            logging.info("Documents backup completed: %s (%d items copied)", docs_backup_dir, copied_items)
            return docs_backup_dir
        else:
            logging.error("Documents backup directory is empty or missing")
            return None

    except OSError as e:
        logging.error("Documents backup failed (%s)", type(e).__name__)
        return None

def create_archive(db_file: Optional[str], docs_dir: Optional[str], timestamp: str, backup_dir: str = "./backups") -> Tuple[Optional[str], Optional[str]]:
    """Create compressed archive of backup files."""
    logging.info("Creating compressed archive...")

    if not db_file or not os.path.isfile(db_file) or not docs_dir or not os.path.isdir(docs_dir):
        logging.error("Cannot create archive without both database and document backups")
        return None, None

    # Create backup directory if it doesn't exist
    os.makedirs(backup_dir, exist_ok=True)

    archive_name = f"dolibarr_backup_{timestamp}.tar.gz"
    archive_path = os.path.join(backup_dir, archive_name)

    try:
        with tarfile.open(archive_path, "w:gz") as tar:
            files_added = 0
            if db_file and os.path.exists(db_file):
                tar.add(db_file, arcname=os.path.basename(db_file))
                logging.info("Added database backup to archive: %s", os.path.basename(db_file))
                files_added += 1
            if docs_dir and os.path.exists(docs_dir):
                tar.add(docs_dir, arcname=os.path.basename(docs_dir))
                logging.info("Added documents backup to archive: %s", os.path.basename(docs_dir))
                files_added += 1

        if files_added == 0:
            logging.warning("Archive created but no files were added!")

        archive_size = os.path.getsize(archive_path)
        logging.info("Archive created: %s (%d bytes)", archive_path, archive_size)
        return archive_path, archive_name
    except Exception as e:
        logging.error("Failed to create archive: %s", e)
        return None, None

def cleanup_files(*files: Optional[str]) -> None:
    """Clean up temporary backup files and directories."""
    logging.info("Cleaning up temporary files...")
    for file_path in files:
        if file_path and os.path.exists(file_path):
            try:
                if os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                    logging.info("Cleaned up directory: %s", file_path)
                else:
                    os.remove(file_path)
                    logging.info("Cleaned up file: %s", file_path)
            except Exception as e:
                logging.error("Failed to clean up %s: %s", file_path, e)

def cleanup_backup_directory(backup_dir: str = "./backups") -> None:
    """Clean up any leftover files in backup directory except final archives."""
    try:
        if not os.path.exists(backup_dir):
            return

        for item in os.listdir(backup_dir):
            item_path = os.path.join(backup_dir, item)

            # Skip files that are final backup archives
            if item.startswith("dolibarr_backup_") and item.endswith(".tar.gz"):
                continue

            # Clean up everything else (temp files, folders, etc.)
            try:
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    logging.info("Cleaned up leftover directory: %s", item)
                else:
                    os.remove(item_path)
                    logging.info("Cleaned up leftover file: %s", item)
            except Exception as e:
                logging.error("Failed to clean up %s: %s", item, e)

    except Exception as e:
        logging.error("Error cleaning backup directory: %s", e)

def debug_environment(db_host: str, db_user: str, db_password: str, documents_path: str) -> None:
    """Debug function to check the environment."""
    logging.info("=== DEBUGGING ENVIRONMENT ===")

    if not os.path.isdir(documents_path):
        logging.warning("Documents path does not exist: %s", documents_path)

    # Check database connectivity
    logging.info("Testing database connection...")
    test_cmd = ['mysql', '--host=' + db_host, '--user=' + db_user, '--execute=SELECT 1;']
    result = run_command(test_cmd, env=_database_environment(db_password))
    if result:
        logging.info("Database connection successful")
    else:
        logging.error("❌ Database connection failed")

    # Check available tools
    logging.info("Checking available tools...")
    for tool in ['mariadb-dump', 'mysqldump', 'mysql', 'cp', 'tar']:
        result = shutil.which(tool)
        if result:
            logging.info("✅ %s: %s", tool, result)
        else:
            logging.error("❌ %s: not found", tool)

    logging.info("=== END DEBUG ===")

def get_env_var(name: str, default: Optional[str] = None) -> str:
    """Get environment variable or exit if required and not found."""
    value = os.getenv(name, default)
    if value is None:
        logging.error("Required environment variable %s is not set", name)
        sys.exit(1)
    return value

def main() -> None:
    """Main backup function."""
    from dotenv import load_dotenv
    load_dotenv()
    logging.info("Starting Dolibarr backup at %s", datetime.datetime.now())

    # Load configuration from environment variables
    DB_HOST = get_env_var('DB_HOST', 'localhost')
    DB_USER = get_env_var('DB_USER', 'root')
    DB_PASSWORD = get_env_var('DB_PASSWORD')
    DB_NAME = get_env_var('DB_NAME')
    SERVICE_ACCOUNT_FILE = get_env_var('SERVICE_ACCOUNT_FILE', './backup-config/service-account.json')
    FOLDER_ID = get_env_var('GOOGLE_DRIVE_FOLDER_ID')
    RETENTION_COUNT = int(get_env_var('BACKUP_RETENTION_COUNT', '7'))
    DOCUMENTS_PATH = get_env_var('DOCUMENTS_PATH')
    BACKUP_DIR = get_env_var('BACKUP_DIR', './backups')

    SCOPES = ['https://www.googleapis.com/auth/drive']

    # Debug environment first
    debug_environment(DB_HOST, DB_USER, DB_PASSWORD, DOCUMENTS_PATH)

    # Initialize Google Drive service
    try:
        drive_service = GoogleDriveService(SERVICE_ACCOUNT_FILE, SCOPES)
    except Exception as e:
        logging.error("Failed to initialize Google Drive service: %s", e)
        sys.exit(1)

    # Check folder access
    if not drive_service.check_folder_access(FOLDER_ID):
        logging.error("Cannot access Google Drive folder: %s", FOLDER_ID)
        sys.exit(1)

    # Generate timestamp for this backup
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # Backup database
    db_backup_file = backup_database(DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, BACKUP_DIR)

    # Backup documents
    docs_backup_dir = backup_documents(timestamp, DOCUMENTS_PATH, BACKUP_DIR)

    if not db_backup_file or not docs_backup_dir:
        logging.error("Backup incomplete; local artifacts retained in %s", BACKUP_DIR)
        sys.exit(1)

    # Create archive
    archive_path, archive_name = create_archive(db_backup_file, docs_backup_dir, timestamp, BACKUP_DIR)

    if archive_path:
        # Check archive size before uploading
        archive_size = os.path.getsize(archive_path)
        if archive_size < 1000:  # Less than 1KB probably means empty
            logging.warning("Archive is very small (%d bytes) - might be empty", archive_size)

        # Upload to Google Drive
        logging.info("Uploading to Google Drive...")
        file_id = drive_service.upload_file(archive_path, archive_name, FOLDER_ID)

        if file_id:
            logging.info("Backup successfully uploaded to Google Drive with ID: %s", file_id)

            # Delete old backups
            logging.info("Managing backup retention...")
            drive_service.delete_old_backups(FOLDER_ID, keep_count=RETENTION_COUNT)

        else:
            logging.error("Upload failed; local artifacts retained in %s", BACKUP_DIR)
            sys.exit(1)
    else:
        logging.error("Archive creation failed; local artifacts retained in %s", BACKUP_DIR)
        sys.exit(1)

    # Remove only artifacts from this successfully uploaded attempt. Previously
    # retained failed backups and unrelated files must remain untouched.
    cleanup_files(*filter(None, [db_backup_file, docs_backup_dir, archive_path]))
    logging.info("Backup completed at %s", datetime.datetime.now())

if __name__ == "__main__":
    main()
