import argparse
import getpass
from sqlalchemy import select, delete
from .db import SessionLocal
from .models import User, Session
from .auth import hasher
from .config import get_settings


def main():
    parser = argparse.ArgumentParser(description="Folio private administration")
    parser.add_argument(
        "command",
        choices=[
            "create-user",
            "reset-password",
            "seed-demo",
            "sync",
            "snapshot",
            "import-local",
        ],
    )
    parser.add_argument("--username", default="owner")
    parser.add_argument("--file")
    args = parser.parse_args()
    with SessionLocal() as db:
        user = db.scalar(
            select(User).where(User.username == args.username.strip().lower())
        )
        if args.command in {"create-user", "reset-password"}:
            if args.command == "create-user" and db.scalar(select(User)):
                raise SystemExit(
                    "This is a single-user application; an owner already exists"
                )
            if args.command == "reset-password" and not user:
                raise SystemExit("User not found")
            password = getpass.getpass("Password (at least 14 characters): ")
            if len(password) < 14 or password != getpass.getpass("Confirm password: "):
                raise SystemExit(
                    "Passwords must match and contain at least 14 characters"
                )
            if not user:
                user = User(
                    username=args.username.strip().lower(),
                    password_hash=hasher.hash(password),
                )
                db.add(user)
            else:
                user.password_hash = hasher.hash(password)
                db.execute(delete(Session).where(Session.user_id == user.id))
            db.commit()
            print("Owner credentials saved")
            return
        if not user:
            raise SystemExit("Run create-user first")
        user_id = user.id
        if args.command == "seed-demo":
            if not get_settings().demo_mode:
                raise SystemExit("Enable DEMO_MODE only in a dedicated demo database")
            from .seed import seed_demo

            seed_demo(db, user_id)
            print("Fictional demo seeded")
            return
    if args.command in {"sync", "import-local"}:
        if get_settings().demo_mode:
            raise SystemExit("Live imports are prohibited in demo mode")
        from .sync import sync_portfolio
        from .sheets import workbook_from_inspection

        if args.command == "import-local" and not args.file:
            raise SystemExit("--file required")
        result = sync_portfolio(
            user_id,
            workbook_from_inspection(args.file)
            if args.command == "import-local"
            else None,
        )
        print(result)
    elif args.command == "snapshot":
        from .sync import take_snapshot

        print(take_snapshot(user_id))


if __name__ == "__main__":
    main()
