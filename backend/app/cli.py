import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from app.config import settings
from app.db import SessionLocal
from app.importer import import_csv
from app.net.ipplan import NetworkPlan
from app.pihole.client import PiholeClient, PiholeError
from app.pihole.sync import apply_sync, plan_sync


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="janus")
    sub = parser.add_subparsers(dest="command", required=True)
    imp = sub.add_parser("import-csv", help="import devices from a CSV export")
    imp.add_argument("path", type=Path)
    imp.add_argument("--dry-run", action="store_true", help="show the report without saving")
    syn = sub.add_parser("sync", help="compare (or apply) Pi-hole reservations")
    syn.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    with SessionLocal() as db:
        if args.command == "import-csv":
            report = import_csv(db, args.path.read_text(encoding="utf-8-sig"), NetworkPlan.from_settings(settings))
            print(json.dumps(asdict(report), indent=2))
            if args.dry_run:
                db.rollback()
            else:
                db.commit()
            return 0
        try:
            with PiholeClient(settings.pihole_url, settings.pihole_password) as client:
                diff = apply_sync(db, client, settings.reservation_lease) if args.apply else plan_sync(
                    db, client, settings.reservation_lease)
        except PiholeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        db.commit()
        print(json.dumps(diff.as_dict(), indent=2))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
