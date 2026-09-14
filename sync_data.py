"""
Syncs data/supermarket_operations_data.xlsx from the project's authoritative
source workbook, and always logs a checksum comparison — so staleness is
caught explicitly rather than assumed away.

Authoritative source: /mnt/project/Supermarket_operations_data.xlsx (the
project's file context, as mounted in Claude's sandbox for this project).
That path only exists inside a Claude conversation with this project open;
pass --source to point at a different location (e.g. running this locally).

This is a required step before rebuilding, reviewing, or committing the repo
in a Claude conversation — run it first, every time, rather than trusting
whatever copy is already sitting in data/. See README.md.

Usage:
    python sync_data.py                      # uses /mnt/project/... as source
    python sync_data.py --source /path/to/Supermarket_operations_data.xlsx
    python sync_data.py --check              # report only, don't copy
"""

from __future__ import annotations
import argparse
import hashlib
import shutil
import sys
from pathlib import Path

DEFAULT_SOURCE = Path("/mnt/project/Supermarket_operations_data.xlsx")
DEST = Path(__file__).parent / "data" / "supermarket_operations_data.xlsx"


def md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="Path to the authoritative workbook")
    parser.add_argument("--check", action="store_true", help="Only report the comparison; don't copy")
    args = parser.parse_args()

    if not args.source.exists():
        print(f"SOURCE NOT FOUND: {args.source}")
        print("This path is only present inside a Claude conversation with this project open.")
        print("Pass --source to point at the workbook explicitly, e.g.:")
        print(f"  python sync_data.py --source /path/to/Supermarket_operations_data.xlsx")
        return 2

    source_hash = md5(args.source)
    dest_exists = DEST.exists()
    dest_hash = md5(DEST) if dest_exists else None

    print(f"Source: {args.source}")
    print(f"  md5: {source_hash}")
    print(f"Dest:   {DEST}")
    print(f"  md5: {dest_hash if dest_exists else '(does not exist)'}")

    if dest_exists and dest_hash == source_hash:
        print("\nIN SYNC — no copy needed.")
        return 0

    if not dest_exists:
        print("\nSTALE — dest does not exist yet.")
    else:
        print("\nSTALE — dest differs from the authoritative source.")

    if args.check:
        print("(--check: not copying)")
        return 1

    DEST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.source, DEST)
    print(f"Copied. New dest md5: {md5(DEST)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
