from __future__ import annotations

import argparse
import random
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from faker import Faker

from bookinglab.config import Config
from bookinglab.schema import SCHEMA_SQL


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed BookingLab data")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--events", type=int, default=120, help="Number of events")
    parser.add_argument("--bookings", type=int, default=5000, help="Number of bookings")
    parser.add_argument("--max-attendees", type=int, default=4, help="Max attendees per booking")
    parser.add_argument("--reset", action="store_true", help="Delete existing DB before seeding")
    return parser.parse_args()


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def main() -> None:
    args = parse_args()
    random.seed(args.seed)
    faker = Faker()
    Faker.seed(args.seed)

    db_path = Path(Config.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if args.reset and db_path.exists():
        db_path.unlink()

    conn = connect(str(db_path))
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()

        conn.execute(
            "INSERT OR IGNORE INTO staff_users (username, display_name, role, pin) VALUES (?, ?, ?, ?)",
            ("admin1", "Admin One", "admin", "1234"),
        )
        conn.execute(
            "INSERT OR IGNORE INTO staff_users (username, display_name, role, pin) VALUES (?, ?, ?, ?)",
            ("staff1", "Staff One", "staff", "1234"),
        )

        now = datetime.now(timezone.utc)
        events = []
        used_slugs = set()

        for i in range(args.events):
            title = f"{faker.catch_phrase()} Summit {i + 1}"
            slug = "".join(ch for ch in title.lower() if ch.isalnum() or ch == " ").strip().replace(" ", "-")
            slug = "-".join(filter(None, slug.split("-")))
            while not slug or slug in used_slugs:
                slug = f"event-{i + 1}-{random.randint(100, 999)}"
            used_slugs.add(slug)

            start_offset = random.randint(-120, 180)
            starts_at = now + timedelta(days=start_offset, hours=random.randint(8, 20))
            ends_at = starts_at + timedelta(hours=random.randint(2, 6))
            capacity = random.randint(40, 300)
            price_cents = random.choice([2500, 4500, 7500, 12000, 20000])

            conn.execute(
                """
                INSERT INTO events (slug, title, description, location, starts_at, ends_at, capacity, price_cents, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    slug,
                    title,
                    faker.paragraph(nb_sentences=3),
                    f"{faker.city()}, {faker.state_abbr()}",
                    starts_at.isoformat(),
                    ends_at.isoformat(),
                    capacity,
                    price_cents,
                    now.isoformat(),
                ),
            )
            event_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            events.append({"id": event_id, "capacity": capacity, "seats_booked": 0})

        statuses = ["requested", "confirmed", "canceled"]
        status_weights = [0.2, 0.7, 0.1]

        booking_count = 0
        attendee_count = 0

        for _ in range(args.bookings):
            seats = random.randint(1, max(1, min(args.max_attendees, 4)))
            eligible = [e for e in events if e["capacity"] - e["seats_booked"] >= seats]
            if not eligible:
                break
            event = random.choice(eligible)

            code = "BK" + "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=6))
            status = random.choices(statuses, weights=status_weights, k=1)[0]

            conn.execute(
                """
                INSERT INTO bookings (event_id, booking_code, status, seats, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event["id"],
                    code,
                    status,
                    seats,
                    faker.sentence(nb_words=6) if random.random() < 0.2 else None,
                    now.isoformat(),
                ),
            )
            booking_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            booking_count += 1

            attendees_to_create = random.randint(1, max(1, min(args.max_attendees, 4)))
            for _ in range(attendees_to_create):
                conn.execute(
                    """
                    INSERT INTO attendees (booking_id, full_name, email, phone, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        booking_id,
                        faker.name(),
                        faker.email(),
                        faker.phone_number() if random.random() < 0.6 else None,
                        now.isoformat(),
                    ),
                )
                attendee_count += 1

            if status != "canceled":
                event["seats_booked"] += seats

        conn.commit()

        print("Seed complete")
        print(f"Events: {len(events)}")
        print(f"Bookings: {booking_count}")
        print(f"Attendees: {attendee_count}")
        total_capacity = sum(e["capacity"] for e in events)
        total_booked = sum(e["seats_booked"] for e in events)
        print(f"Capacity used: {total_booked}/{total_capacity}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
