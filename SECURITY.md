# Security

Keep database credentials, Google service-account keys, Drive folder identifiers, logs and backup archives outside Git. `.env.example` contains placeholders only. Restrict `.env` and service-account JSON files to the account running the backup (`chmod 600`).

Install [Gitleaks](https://github.com/gitleaks/gitleaks) and enable the local pre-push check:

```bash
git config core.hooksPath .githooks
python3 scripts/check_public_files.py
gitleaks git . --config .gitleaks.toml --log-opts="--all --full-history" --gitleaks-ignore-path /dev/null --ignore-gitleaks-allow --redact=100
```

The file-boundary check rejects runtime credentials and backup files in the index or reachable history. CI repeats the boundary and secret scans, and runs only offline tests. Never bypass these checks or import an older repository's objects into this source history.

If a credential is accidentally published, revoke or rotate it at its issuer promptly. Removing it from the latest source or deleting a repository does not invalidate copies that others may have downloaded. Follow [GitHub's sensitive-data removal guidance](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository) for cached or historical copies.

Do not put credentials, customer records or backup data in public issues. Report a vulnerability privately to mail@kreativitat.com with a redacted description and affected source location.
