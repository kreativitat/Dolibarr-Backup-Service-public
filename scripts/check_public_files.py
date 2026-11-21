#!/usr/bin/env python3
"""Reject private runtime files in the Git index or reachable history."""
import json
import subprocess
import sys
from pathlib import PurePosixPath


def git(*args):
    return subprocess.check_output(["git", *args])


def restricted(path):
    parts = PurePosixPath(path).parts
    name = parts[-1].lower()
    if path == ".env.example":
        return False
    private_dirs = {"backup-config", "backups", "logs", ".venv", "venv"}
    return (
        any(part.lower() in private_dirs for part in parts[:-1])
        or name == ".env"
        or name.startswith(".env.")
        or name.endswith(".env")
        or name.endswith((".pem", ".key", ".p12", ".pfx", ".sql", ".dump", ".zip", ".tar", ".tgz", ".gz", ".bz2", ".xz", ".zst", ".7z", ".rar", ".bak", ".sqlite", ".sqlite3", ".log"))
        or (name.endswith(".json") and ("service-account" in name or "credentials" in name))
    )


def main():
    indexed = git("ls-files", "-z").decode().split("\0")
    # New initial trees have no HEAD yet; their index is still checked.
    exists = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], capture_output=True).returncode == 0
    historical = []
    if exists:
        changes = git("-c", "core.quotePath=false", "log", "--all", "--format=", "--name-only", "-z")
        historical = [p.strip("\n") for p in changes.decode().split("\0")]
    blocked = sorted({p for p in indexed + historical if p and restricted(p)})
    for path in indexed:
        if not path or not path.lower().endswith(".json"):
            continue
        try:
            content = json.loads(git("show", ":" + path))
        except (ValueError, subprocess.CalledProcessError):
            continue
        if isinstance(content, dict) and (content.get("private_key") or content.get("type") == "service_account"):
            blocked.append(path)
    if blocked:
        print("Private runtime files must not enter public source:", file=sys.stderr)
        for path in sorted(set(blocked)):
            print(" - " + path, file=sys.stderr)
        return 1
    print("Public file boundary check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
