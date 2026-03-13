"""Seed script to populate the database with sample data.

Run inside the Docker container:
    docker compose exec web python scripts/seed.py
"""

from passlib.context import CryptContext

from app.db.database import Base, SessionLocal, engine
from app.models.child import Child
from app.models.story import Story, StoryStatus
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
        db.flush()  # Assign IDs before referencing them

        # --- Children ---
        emma = Child(user_id=alice.id, name="Emma", age=5)
        liam = Child(user_id=alice.id, name="Liam", age=8)
        noah = Child(user_id=bob.id, name="Noah", age=6)
        db.add_all([emma, liam, noah])
        db.flush()

        # --- Stories ---
        stories = [
            Story(
                child_id=emma.id,
                theme="space adventure",
                title="Emma and the Star Pirates",
                content=(
                    "One night, Emma looked up at the sky and noticed a tiny spaceship blinking "
                    "near the moon. She climbed aboard and met Captain Comet, a friendly robot "
                    "who needed help collecting lost stars. Together they zoomed through the "
                    "galaxy, returning each star to its place, and made it home by sunrise."
                ),
                audio_url="https://storage.example.com/audio/emma-star-pirates.mp3",
                status=StoryStatus.COMPLETED,
            ),
            Story(
                child_id=emma.id,
                theme="forest animals",
                title="The Sleepy Fox",
                content=(
                    "Deep in the Whispering Woods lived a little fox named Finn who could never "
                    "fall asleep. An old owl taught him to count fireflies, and on the very first "
                    "try Finn drifted off dreaming of golden meadows."
                ),
                audio_url=None,
                status=StoryStatus.GENERATING_AUDIO,
            ),
            Story(
                child_id=liam.id,
                theme="underwater treasure",
                title="Liam and the Pearl Kingdom",
                content=(
                    "Liam found a golden shell on the beach that whispered directions to the "
                    "Pearl Kingdom beneath the waves. With the help of a clever dolphin he solved "
                    "three riddles, freed the captured mermaids, and returned the Pearl Crown to "
                    "its rightful queen."
                ),
                audio_url="https://storage.example.com/audio/liam-pearl-kingdom.mp3",
                status=StoryStatus.COMPLETED,
            ),
            Story(
                child_id=noah.id,
                theme="dinosaur park",
                title=None,
                content=None,
                audio_url=None,
                status=StoryStatus.GENERATING_TEXT,
            ),
        ]
        db.add_all(stories)
        db.commit()

        print("Seed completed successfully.")
        print(f"  Users  : alice@example.com, bob@example.com  (password: password123)")
        print(f"  Children: Emma (5), Liam (8) → Alice | Noah (6) → Bob")
        print(f"  Stories : {len(stories)} stories created")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
