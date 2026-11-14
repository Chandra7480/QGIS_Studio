#!/usr/bin/env python3
"""Universal AI GIS Studio — Audit Log Verification CLI.

Verifies the SHA256 hash chain integrity of audit logs.
Can also verify against external anchors.

Usage:
    python -m monitoring.verify_audit              # Verify full chain
    python -m monitoring.verify_audit --start 100  # Verify from entry 100
    python -m monitoring.verify_audit --end 500    # Verify up to entry 500
    python -m monitoring.verify_audit --anchors    # Also verify external anchors
    python -m monitoring.verify_audit --db-path /path/to/db.sqlite
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db import Database
from database.repositories.audit_repository import AuditRepository
from core.logging import setup_logging


def main():
    parser = argparse.ArgumentParser(
        description="Verify UAGIS audit log hash chain integrity",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--db-path", default=None,
                        help="Path to SQLite database (default: from config)")
    parser.add_argument("--start", type=int, default=1,
                        help="Start verification from this entry ID (default: 1)")
    parser.add_argument("--end", type=int, default=None,
                        help="End verification at this entry ID (default: latest)")
    parser.add_argument("--anchors", action="store_true",
                        help="Also verify external anchors")
    parser.add_argument("--anchor-file", default=None,
                        help="Path to external anchor file (default: ./audit_anchors.log)")
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="Only output errors")

    args = parser.parse_args()

    # Setup logging
    setup_logging(level="WARNING" if args.quiet else "INFO")

    # Resolve database path
    if args.db_path:
        db_path = Path(args.db_path)
    else:
        # Try default locations
        import os
        data_dir = os.environ.get("LOCALAPPDATA") or str(Path.home())
        db_path = Path(data_dir) / "Universal AI GIS Studio" / "uagis.db"

    if not db_path.exists():
        print(f"ERROR: Database not found at {db_path}", file=sys.stderr)
        sys.exit(1)

    # Open database
    db = Database(str(db_path))
    db.connect()
    repo = AuditRepository(db)

    # Verify hash chain
    result = repo.verify_chain(args.start, args.end)

    # Output results
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("=" * 60)
        print("UAGIS Audit Log Verification")
        print("=" * 60)
        print(f"Database: {db_path}")
        print(f"Range: {args.start} to {args.end or 'latest'}")
        print(f"Total checked: {result['total_checked']}")
        print(f"Verified: {result['verified_count']}")
        print(f"Last hash: {result['last_hash']}")
        print(f"Chain valid: {'YES' if result['verified'] else 'NO'}")
        print("=" * 60)

        if result["errors"]:
            print("\nERRORS FOUND:")
            for err in result["errors"]:
                print(f"  Entry {err['id']}: hash mismatch")
                print(f"    Expected: {err['expected_hash']}")
                print(f"    Stored:   {err['stored_hash']}")
                print(f"    Time:     {err['timestamp']}")
            print("=" * 60)
            sys.exit(1)
        else:
            print("\n✓ Hash chain verified successfully")

    # Verify external anchors if requested
    if args.anchors:
        verify_anchors(repo, args.anchor_file, args.json, args.quiet)

    if not result["verified"]:
        sys.exit(1)


def verify_anchors(repo: AuditRepository, anchor_file: str | None, json_output: bool, quiet: bool):
    """Verify external anchors against audit log hashes."""
    if anchor_file is None:
        anchor_file = str(Path.cwd() / "audit_anchors.log")

    anchor_path = Path(anchor_file)
    if not anchor_path.exists():
        msg = f"Anchor file not found: {anchor_path}"
        if json_output:
            print(json.dumps({"anchors_verified": False, "error": msg}))
        else:
            print(f"\nWARNING: {msg}")
        return

    anchors = repo.get_anchors()
    if not anchors:
        msg = "No anchors found in database"
        if json_output:
            print(json.dumps({"anchors_verified": False, "error": msg}))
        else:
            print(f"\nWARNING: {msg}")
        return

    verified = 0
    errors = []

    for anchor in anchors:
        # Get the audit log entry
        row = repo.db.fetchone(
            "SELECT audit_hash FROM audit_logs WHERE id = ?", (anchor["audit_log_id"],)
        )
        if not row:
            errors.append({
                "audit_log_id": anchor["audit_log_id"],
                "error": "Audit log entry not found",
            })
            continue

        if row["audit_hash"] != anchor["anchor_hash"]:
            errors.append({
                "audit_log_id": anchor["audit_log_id"],
                "error": "Anchor hash mismatch",
                "db_hash": row["audit_hash"],
                "anchor_hash": anchor["anchor_hash"],
            })
            continue

        # Also check against external file
        try:
            with open(anchor_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    ext_anchor = json.loads(line)
                    if ext_anchor.get("audit_log_id") == anchor["audit_log_id"]:
                        if ext_anchor.get("anchor_hash") != anchor["anchor_hash"]:
                            errors.append({
                                "audit_log_id": anchor["audit_log_id"],
                                "error": "External anchor file hash mismatch",
                                "file_hash": ext_anchor.get("anchor_hash"),
                                "db_hash": anchor["anchor_hash"],
                            })
                        break
        except Exception as exc:
            errors.append({
                "audit_log_id": anchor["audit_log_id"],
                "error": f"Failed to read anchor file: {exc}",
            })

        verified += 1

    if json_output:
        print(json.dumps({
            "anchors_verified": len(errors) == 0,
            "total_anchors": len(anchors),
            "verified": verified,
            "errors": errors,
        }, indent=2))
    else:
        print(f"\nExternal Anchors: {verified}/{len(anchors)} verified")
        if errors:
            print("ANCHOR ERRORS:")
            for err in errors:
                print(f"  Entry {err['audit_log_id']}: {err['error']}")
            sys.exit(1)
        else:
            print("✓ All external anchors verified")


if __name__ == "__main__":
    main()