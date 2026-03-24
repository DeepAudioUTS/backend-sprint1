"""Seed script to populate the database with sample data.

Run inside the Docker container:
    docker compose exec web python scripts/seed.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from passlib.context import CryptContext

from app.db.database import Base, SessionLocal, engine
from app.models.child import Child
from app.models.story import Story
from app.models.story_draft import StoryDraft
from app.models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def seed() -> None:
    """Create all tables and insert sample data."""
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Skip if data already exists
        if db.query(User).count() > 0:
            print("Database already contains data. Skipping seed.")
            return

        # --- Users ---
        alice = User(
            name="Alice Johnson",
            email="alice@example.com",
            hashed_password=pwd_context.hash("password123"),
            subscription_plan="premium",
        )
        bob = User(
            name="Bob Smith",
            email="bob@example.com",
            hashed_password=pwd_context.hash("password123"),
            subscription_plan="free",
        )
        db.add_all([alice, bob])
        db.flush()

        # --- Children ---
        emma = Child(user_id=alice.id, name="Emma", age=5)
        liam = Child(user_id=alice.id, name="Liam", age=8)
        noah = Child(user_id=bob.id, name="Noah", age=6)
        db.add_all([emma, liam, noah])
        db.flush()
        db.commit()

        print("Seed completed successfully.")
        print("  Users   : alice@example.com, bob@example.com  (password: password123)")
        print("  Children: Emma (5), Liam (8) → Alice | Noah (6) → Bob")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
