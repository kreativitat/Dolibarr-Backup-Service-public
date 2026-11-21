# Dolibarr Backup Service

A Python-based backup solution for Dolibarr ERP/CRM with automated Google Drive uploads and retention management.

## Features

- 🔄 Automated database backups (MariaDB/MySQL)
- 📁 Document directory backups
- ☁️ Google Drive integration with automatic uploads
- 🗑️ Configurable backup retention (auto-cleanup old backups)
- ⏰ Cron scheduling support
- 🔒 Secure credential management via environment variables
- 📝 Centralized logging with rotation
- 🔄 Retry logic with exponential backoff for uploads
- 🐍 Type-hinted Python code for maintainability

## Prerequisites

- Python 3.8 or higher
- MySQL/MariaDB client tools (`mysql`, `mariadb-dump`)
- Google Cloud service account with Google Drive API access
- Service account JSON key file

### Installing MySQL/MariaDB Client

**Ubuntu/Debian:**
```bash
sudo apt-get install mariadb-client
```

**macOS:**
```bash
brew install mariadb
```

**CentOS/RHEL:**
```bash
sudo yum install mariadb
```

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/kreativitat/Dolibarr-Backup-Service-public.git
cd Dolibarr-Backup-Service-public
```

### 2. Run the setup script

```bash
chmod +x setup.sh
./setup.sh
```

This will:
- Create a Python virtual environment
- Install all dependencies
- Create necessary directories (`backups/`, `logs/`, `backup-config/`)
- Create `.env` file from template

### 3. Configure environment variables

Edit the `.env` file with your credentials:

```bash
# Database Configuration
DB_HOST=localhost
DB_NAME=your_database_name
DB_USER=root
DB_PASSWORD=your_password

# Google Drive Backup Configuration
GOOGLE_DRIVE_FOLDER_ID=your_folder_id_here
SERVICE_ACCOUNT_FILE=./backup-config/service-account.json
BACKUP_RETENTION_COUNT=7

# Paths
DOCUMENTS_PATH=/var/www/html/documents
BACKUP_DIR=./backups

# Logging
LOG_DIR=./logs
LOG_LEVEL=INFO
```

### 4. Setup Google Drive API

1. Create a Google Cloud project
2. Enable the Google Drive API
3. Create a service account and download the JSON key
4. Place the key at `backup-config/service-account.json`
5. Share your target Google Drive folder with the service account email

### 5. Run your first backup

```bash
source venv/bin/activate
python3 backup.py
```

## Scheduling Automated Backups

### Using Cron (Linux/macOS)

Add to your crontab:

```bash
crontab -e
```

Add this line (runs daily at 3 AM):

```
0 3 * * * cd /path/to/Dolibarr-Backup-Service && venv/bin/python3 backup.py >> logs/cron.log 2>&1
```

### Cron Schedule Examples

- `0 3 * * *` - Daily at 3 AM
- `0 */6 * * *` - Every 6 hours
- `0 2 * * 0` - Weekly on Sunday at 2 AM
- `0 0 1 * *` - Monthly on the 1st at midnight

### Using systemd (Linux)

Create a service file at `/etc/systemd/system/dolibarr-backup.service`:

```ini
[Unit]
Description=Dolibarr Backup Service
After=network.target

[Service]
Type=oneshot
User=your_user
WorkingDirectory=/path/to/Dolibarr-Backup-Service
ExecStart=/path/to/Dolibarr-Backup-Service/venv/bin/python3 backup.py
EnvironmentFile=/path/to/Dolibarr-Backup-Service/.env

[Install]
WantedBy=multi-user.target
```

Create a timer file at `/etc/systemd/system/dolibarr-backup.timer`:

```ini
[Unit]
Description=Run Dolibarr Backup Daily

[Timer]
OnCalendar=daily
OnCalendar=03:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start the timer:

```bash
sudo systemctl daemon-reload
sudo systemctl enable dolibarr-backup.timer
sudo systemctl start dolibarr-backup.timer
```

## Project Structure

```
.
├── backup.py                 # Main backup script
├── logging_config.py        # Logging configuration with rotation
├── test_backup.py           # Offline security and orchestration tests
├── test_cleanup.py          # Cleanup tests with synthetic temporary files
├── setup.sh                 # Setup script
├── requirements.txt         # Python dependencies
├── .env                     # Environment variables (git-ignored)
├── .env.example            # Environment variables template
├── .gitignore              # Git ignore rules
├── backup-config/
│   └── service-account.json # Google service account key (git-ignored)
├── backups/                 # Backup files (git-ignored)
└── logs/                    # Log files (git-ignored)
```

## Backup Process

1. **Database Backup**: Creates a SQL dump of the MariaDB database
2. **Document Backup**: Copies the Dolibarr documents directory
3. **Archive Creation**: Compresses both into a `.tar.gz` file
4. **Upload**: Uploads to Google Drive with retry logic (3 attempts with exponential backoff)
5. **Cleanup**: Removes old backups based on retention policy
6. **Local Cleanup**: Removes only this run's temporary files after successful upload; failed or incomplete backups are retained for recovery.

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DB_HOST` | Yes | `localhost` | Database host |
| `DB_NAME` | Yes | - | Database name |
| `DB_USER` | Yes | `root` | Database user |
| `DB_PASSWORD` | Yes | - | Database password |
| `GOOGLE_DRIVE_FOLDER_ID` | Yes | - | Google Drive folder ID |
| `SERVICE_ACCOUNT_FILE` | No | `./backup-config/service-account.json` | Service account key path |
| `BACKUP_RETENTION_COUNT` | No | `7` | Number of backups to keep |
| `DOCUMENTS_PATH` | Yes | - | Path to Dolibarr documents directory |
| `BACKUP_DIR` | No | `./backups` | Local backup directory |
| `LOG_DIR` | No | `./logs` | Log directory |
| `LOG_LEVEL` | No | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

## Monitoring and Logs

### View Recent Logs

```bash
tail -f logs/backup.log
```

### View Cron Logs

```bash
tail -f logs/cron.log
```

### Log Rotation

Logs are automatically rotated when they reach 10MB, keeping 5 backup files.

## Testing

Run the offline checks from an isolated environment:

```bash
python3 -m unittest discover -v
python3 -m py_compile backup.py logging_config.py test_backup.py test_cleanup.py scripts/check_public_files.py
bash -n setup.sh
python3 scripts/check_public_files.py
```

Tests use mocked subprocess/Google Drive operations and synthetic temporary files. They do not load your `.env`, access a live database or Drive folder, or clean your configured backup directory. CI verifies Python 3.11. A live backup is an operational action, not a test command.

## Preventing credential publication

Only `.env.example` belongs in Git. Keep `.env`, service-account JSON, `backup-config/`, `backups/` and `logs/` private. After placing your key, restrict its permissions:

```bash
chmod 600 .env backup-config/service-account.json
```

Install [Gitleaks](https://github.com/gitleaks/gitleaks), then enable the pre-push hook:

```bash
git config core.hooksPath .githooks
```

The hook and CI scan all reachable history and reject private runtime paths. See [SECURITY.md](SECURITY.md). Do not import an older repository's Git objects into this source history.

## Troubleshooting

### Backup fails with "Cannot connect to database"

Check database credentials in `.env` and ensure MariaDB is running:

```bash
mysql --host="$DB_HOST" --user="$DB_USER" --password -e "SHOW DATABASES;"
```

### Google Drive upload fails

1. Verify service account JSON is correctly placed
2. Check that the Google Drive folder is shared with the service account email
3. Verify `GOOGLE_DRIVE_FOLDER_ID` in `.env`

### "Command not found: mysql" or "mariadb-dump"

Install MySQL/MariaDB client tools (see Prerequisites section).

### Permission denied errors

Ensure the user running the backup has:
- Read access to the documents directory
- Write access to the backup directory
- Write access to the logs directory

## Backup Restore

To restore from a backup:

1. Download the backup `.tar.gz` from Google Drive
2. Extract the archive:
   ```bash
   tar -xzf dolibarr_backup_YYYYMMDD_HHMMSS.tar.gz
   ```
3. Restore the database:
   ```bash
   mysql --host="$DB_HOST" --user="$DB_USER" --password "$DB_NAME" < dolibarr_db_YYYYMMDD_HHMMSS.sql
   ```
4. Restore documents:
   ```bash
   cp -r dolibarr_documents_YYYYMMDD_HHMMSS/* /path/to/dolibarr/documents/
   ```

## Security Features

- ✅ Runtime credentials stay in private environment/configuration files
- ✅ Private runtime files rejected by a file-boundary check and secret scanning
- ✅ Database passwords kept out of command arguments and logs
- ✅ Type hints and robust error handling in Python code
- ✅ Retry logic for network operations
- ✅ Log rotation to prevent disk space issues

## Updating

To update the backup service:

```bash
git pull
source venv/bin/activate
pip install -r requirements.txt --upgrade
```

## Uninstalling

To remove the backup service:

```bash
# Remove from crontab
crontab -e  # Delete the backup line

# Or disable systemd timer
sudo systemctl stop dolibarr-backup.timer
sudo systemctl disable dolibarr-backup.timer

# Remove the directory
cd ..
rm -rf Dolibarr-Backup-Service
```

## Support

For issues and questions, please open a GitHub issue.

## License

See [LICENSE](LICENSE) file for details.
