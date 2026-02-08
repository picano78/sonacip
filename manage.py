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


def cmd_reset_password(args) -> int:
    from app import db
    from app.models import User

    app = _create_app()
    with app.app_context():
        user = User.query.filter_by(email=args.email).first()
        if not user:
            print(f"Utente con email '{args.email}' non trovato.")
            return 1
        user.set_password(args.password)
        db.session.commit()
        print(f"Password aggiornata per {user.email} (id={user.id}, role={user.role})")
    return 0


def cmd_check_admin(_args) -> int:
    from app import db
    from app.models import User

    app = _create_app()
    with app.app_context():
        admins = User.query.filter_by(role='super_admin').all()
        if not admins:
            admins = User.query.filter(User.role.in_(['super_admin', 'admin'])).all()
        if not admins:
            print("Nessun super admin trovato. Esegui: python manage.py seed")
            return 1
        for u in admins:
            can_login = u.check_password("Simone78")
            print(f"id={u.id} email={u.email} username={u.username} role={u.role} "
                  f"active={u.is_active} password_ok={can_login}")
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

    rp_parser = sub.add_parser("reset-password", help="Reset password per un utente")
    rp_parser.add_argument("email", help="Email dell'utente")
    rp_parser.add_argument("password", help="Nuova password")
    rp_parser.set_defaults(func=cmd_reset_password)

    ca_parser = sub.add_parser("check-admin", help="Verifica stato super admin")
    ca_parser.set_defaults(func=cmd_check_admin)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

