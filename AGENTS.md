# Dolibarr Backup Service

Standalone Python utility for MariaDB/MySQL and Dolibarr document backups with Google Drive uploads. This is not a Dolibarr PHP module.

- `backup.py` owns backup orchestration and Drive operations; `logging_config.py` owns logging. `setup.sh` prepares the existing native Python environment. CI uses Python 3.11.
- Install dependencies in an isolated virtual environment from `requirements.txt`. Run `python3 -m unittest discover -v`, `python3 -m py_compile backup.py logging_config.py test_backup.py test_cleanup.py scripts/check_public_files.py`, `bash -n setup.sh`, and `python3 scripts/check_public_files.py`.
- Tests must use mocks and temporary synthetic files. Never invoke live database/Drive writes or retention deletion as verification.
- `.env`, service-account keys, `backup-config/`, `backups/`, and `logs/` are private runtime data. Publish only placeholder configuration. Never log credentials, SQL dumps, or document contents, and never pass passwords in command arguments.
- Preserve failed-backup artifacts. Do not expand deletion or run retention after an incomplete or failed upload.
- Develop on `main`. Enable the repository pre-push hook with `git config core.hooksPath .githooks`; Gitleaks must be available. Secret scanning covers all reachable history.
- This repository contains a fresh source history. Never fetch, merge, or push objects from a repository that previously contained private runtime data.
- Publishing source does not deploy the service. Any future installation, credentials, scheduling or production operation requires a separately identified target and authorization. See `README.md` and `SECURITY.md`.
- Preserve the MIT licence and historical copyright attribution. New project-owned documentation uses Kreativität Works <mail@kreativitat.com>.
