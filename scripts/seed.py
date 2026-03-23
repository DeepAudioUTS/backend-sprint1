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

        # --- Completed stories (Story record, no draft) ---
        completed_stories = [
            Story(
                child_id=emma.id,
                theme="space adventure",
                title="Emma and the Star Pirates",
                abstracts=[
                    "A brave girl joins a friendly robot captain to collect lost stars and save the galaxy.",
                    "Emma discovers a spaceship and goes on a midnight mission to light up the sky.",
                    "A young explorer teams up with alien friends to rescue a stolen constellation.",
                ],
                abstract="A brave girl joins a friendly robot captain to collect lost stars and save the galaxy.",
                content=(
                    "One night, Emma looked up at the sky and noticed a tiny spaceship blinking "
                    "near the moon. She climbed aboard and met Captain Comet, a friendly robot "
                    "who needed help collecting lost stars. Together they zoomed through the "
                    "galaxy, returning each star to its place, and made it home by sunrise."
                ),
                audio_url="https://storage.example.com/audio/emma-star-pirates.mp3",
            ),
            Story(
                child_id=liam.id,
                theme="underwater treasure",
                title="Liam and the Pearl Kingdom",
                abstracts=[
                    "A boy follows a magical shell's directions to rescue mermaids and restore a kingdom.",
                    "Liam dives deep and discovers a secret city where fish have forgotten how to sing.",
                    "A young diver finds a treasure map that leads to the heart of the ocean.",
                ],
                abstract="A boy follows a magical shell's directions to rescue mermaids and restore a kingdom.",
                content=(
                    "Liam found a golden shell on the beach that whispered directions to the "
                    "Pearl Kingdom beneath the waves. With the help of a clever dolphin he solved "
                    "three riddles, freed the captured mermaids, and returned the Pearl Crown to "
                    "its rightful queen."
                ),
                audio_url="https://storage.example.com/audio/liam-pearl-kingdom.mp3",
            ),
        ]
        db.add_all(completed_stories)
        db.flush()

        # --- In-progress story (StoryDraft only, no Story yet) ---
        # Noah has a story being created — abstract selected, text being generated
        noah_draft = StoryDraft(
            child_id=noah.id,
            theme="jungle explorer",
            abstracts=[
                "Noah swings through the trees and befriends a lost baby elephant.",
                "A boy discovers a hidden jungle city and must help its animal guardians.",
                "Noah follows a mysterious map into the jungle and meets a wise old parrot.",
            ],
            selected_abstract="Noah swings through the trees and befriends a lost baby elephant.",
        )
        db.add(noah_draft)
        db.commit()

        print("Seed completed successfully.")
        print("  Users   : alice@example.com, bob@example.com  (password: password123)")
        print("  Children: Emma (5), Liam (8) → Alice | Noah (6) → Bob")
        print(f"  Stories : {len(completed_stories)} completed stories")
        print("  Drafts  : 1 in-progress draft (Noah, status: generating_text)")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
