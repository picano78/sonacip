#!/usr/bin/env python3
"""
SONACIP management commands (no Flask CLI required).

Usage:
  python manage.py db upgrade
  python manage.py seed
"""
from __future__ import annotations

import argparse
import sys


def _create_app():
    from app import create_app

    return create_app()


def cmd_db_upgrade(_args) -> int:
    from flask_migrate import upgrade

    app = _create_app()
    migrations_dir = app.config.get("MIGRATIONS_DIR", "migrations")
    with app.app_context():
        upgrade(directory=migrations_dir)
    return 0


def cmd_seed(_args) -> int:
    from app.core.seed import seed_defaults

    app = _create_app()
    summary = seed_defaults(app)
    for k, v in summary.items():
        print(f"{k}={v}")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="manage.py")
    sub = parser.add_subparsers(dest="cmd", required=True)

    db_parser = sub.add_parser("db", help="Database commands")
    db_sub = db_parser.add_subparsers(dest="db_cmd", required=True)
    db_up = db_sub.add_parser("upgrade", help="Run migrations")
    db_up.set_defaults(func=cmd_db_upgrade)

    seed_parser = sub.add_parser("seed", help="Seed baseline data")
    seed_parser.set_defaults(func=cmd_seed)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

