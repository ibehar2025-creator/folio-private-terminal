"""Consistent local SQLite backup. PostgreSQL uses pg_dump (see README)."""

import argparse
import sqlite3
from pathlib import Path
from .config import get_settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("destination")
    args = parser.parse_args()
    url = get_settings().database_url
    if not url.startswith("sqlite:///"):
        raise SystemExit("Use pg_dump for PostgreSQL backups")
    source = Path(url.removeprefix("sqlite:///")).resolve()
    target = Path(args.destination).resolve()
    if source == target or target.exists():
        raise SystemExit(
            "Choose a new destination; existing files are never overwritten"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:
        src.backup(dst)
    print("Consistent SQLite backup created. Treat it as private financial data.")


if __name__ == "__main__":
    main()
