"""Create a local demo with a unique random password; never a public demo account."""

import json
import secrets
from pathlib import Path
from sqlalchemy import select
from .config import get_settings
from .db import SessionLocal
from .models import User
from .auth import hasher
from .seed import seed_demo


def main():
    c = get_settings()
    if not c.demo_mode or c.environment == "production":
        raise SystemExit("This command requires a local DEMO_MODE=true database")
    with SessionLocal() as db:
        if db.scalar(select(User)):
            raise SystemExit(
                "Owner already exists; demo setup does not replace credentials or data"
            )
        password = secrets.token_urlsafe(24)
        user = User(username="owner", password_hash=hasher.hash(password))
        db.add(user)
        db.commit()
        seed_demo(db, user.id)
    target = Path("data/demo-login.json")
    target.parent.mkdir(exist_ok=True)
    target.write_text(
        json.dumps({"username": "owner", "password": password}, indent=2),
        encoding="utf-8",
    )
    print(
        "Fictional demo created. Your unique local credentials are in backend/data/demo-login.json (Git ignored)."
    )


if __name__ == "__main__":
    main()
