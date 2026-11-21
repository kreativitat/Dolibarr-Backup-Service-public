# Changelog

## Unreleased

- Publish a sanitized source snapshot with a fresh Git history.
- Reject runtime credentials, logs and backup archives from public source; scan all reachable history locally and in CI.
- Remove database passwords and SQL output from command logging and process arguments.
- Replace live upload/cleanup checks with isolated offline regression tests.
- Preserve recoverable artifacts after failed or incomplete backups and run retention only after successful upload.
