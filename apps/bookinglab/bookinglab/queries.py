from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlstratum import (
    SELECT,
    INSERT,
    UPDATE,
    COUNT,
    SUM,
    MIN,
    AND,
    OR,
    Table,
    col,
)
from sqlstratum.hydrate.pydantic import using_pydantic

from bookinglab.models import EventOut, AttendeeOut


events = Table(
    "events",
    col("id", int),
    col("slug", str),
    col("title", str),
    col("description", str),
    col("location", str),
    col("starts_at", str),
    col("ends_at", str),
    col("capacity", int),
    col("price_cents", int),
    col("created_at", str),
)

bookings = Table(
    "bookings",
    col("id", int),
    col("event_id", int),
    col("booking_code", str),
    col("status", str),
    col("seats", int),
    col("notes", str),
    col("created_at", str),
)

attendees = Table(
    "attendees",
    col("id", int),
    col("booking_id", int),
    col("full_name", str),
    col("email", str),
    col("phone", str),
    col("created_at", str),
)

staff_users = Table(
    "staff_users",
    col("id", int),
    col("username", str),
    col("display_name", str),
    col("role", str),
    col("pin", str),
)

payments = Table(
    "payments",
    col("id", int),
    col("booking_id", int),
    col("method", str),
    col("paid_cents", int),
    col("paid_at", str),
)


def get_staff_login(runner, username: str, pin: str):
    q = (
        SELECT(
            staff_users.c.id.AS("id"),
            staff_users.c.username.AS("username"),
            staff_users.c.display_name.AS("display_name"),
            staff_users.c.role.AS("role"),
        )
        .FROM(staff_users)
        .WHERE(staff_users.c.username == username, staff_users.c.pin == pin)
    )
    return runner.fetch_one(q)


def list_upcoming_events(runner, limit: int = 20):
    now_iso = datetime.utcnow().isoformat()
    q = using_pydantic(
        SELECT(
            events.c.id.AS("id"),
            events.c.slug.AS("slug"),
            events.c.title.AS("title"),
            events.c.description.AS("description"),
            events.c.location.AS("location"),
            events.c.starts_at.AS("starts_at"),
            events.c.ends_at.AS("ends_at"),
            events.c.capacity.AS("capacity"),
            events.c.price_cents.AS("price_cents"),
            events.c.created_at.AS("created_at"),
            SUM(bookings.c.seats).AS("seats_booked"),
        )
        .FROM(events)
        .LEFT_JOIN(bookings, ON=AND(bookings.c.event_id == events.c.id, bookings.c.status != "canceled"))
        .WHERE(events.c.starts_at >= now_iso)
        .GROUP_BY(events.c.id)
        .ORDER_BY(events.c.starts_at.ASC())
        .LIMIT(limit)
    ).hydrate(EventOut)
    return runner.fetch_all(q)


def get_event_by_slug(runner, slug: str):
    q = using_pydantic(
        SELECT(
            events.c.id.AS("id"),
            events.c.slug.AS("slug"),
            events.c.title.AS("title"),
            events.c.description.AS("description"),
            events.c.location.AS("location"),
            events.c.starts_at.AS("starts_at"),
            events.c.ends_at.AS("ends_at"),
            events.c.capacity.AS("capacity"),
            events.c.price_cents.AS("price_cents"),
            events.c.created_at.AS("created_at"),
            SUM(bookings.c.seats).AS("seats_booked"),
        )
        .FROM(events)
        .LEFT_JOIN(bookings, ON=AND(bookings.c.event_id == events.c.id, bookings.c.status != "canceled"))
        .WHERE(events.c.slug == slug)
        .GROUP_BY(events.c.id)
        .LIMIT(1)
    ).hydrate(EventOut)
    return runner.fetch_one(q)


def get_event_by_id(runner, event_id: int):
    q = using_pydantic(
        SELECT(
            events.c.id.AS("id"),
            events.c.slug.AS("slug"),
            events.c.title.AS("title"),
            events.c.description.AS("description"),
            events.c.location.AS("location"),
            events.c.starts_at.AS("starts_at"),
            events.c.ends_at.AS("ends_at"),
            events.c.capacity.AS("capacity"),
            events.c.price_cents.AS("price_cents"),
            events.c.created_at.AS("created_at"),
            SUM(bookings.c.seats).AS("seats_booked"),
        )
        .FROM(events)
        .LEFT_JOIN(bookings, ON=AND(bookings.c.event_id == events.c.id, bookings.c.status != "canceled"))
        .WHERE(events.c.id == event_id)
        .GROUP_BY(events.c.id)
        .LIMIT(1)
    ).hydrate(EventOut)
    return runner.fetch_one(q)


def list_events(runner, limit: int, offset: int):
    q = using_pydantic(
        SELECT(
            events.c.id.AS("id"),
            events.c.slug.AS("slug"),
            events.c.title.AS("title"),
            events.c.location.AS("location"),
            events.c.starts_at.AS("starts_at"),
            events.c.ends_at.AS("ends_at"),
            events.c.capacity.AS("capacity"),
            events.c.price_cents.AS("price_cents"),
            events.c.created_at.AS("created_at"),
            SUM(bookings.c.seats).AS("seats_booked"),
        )
        .FROM(events)
        .LEFT_JOIN(bookings, ON=AND(bookings.c.event_id == events.c.id, bookings.c.status != "canceled"))
        .GROUP_BY(events.c.id)
        .ORDER_BY(events.c.starts_at.DESC())
        .LIMIT(limit)
        .OFFSET(offset)
    ).hydrate(EventOut)
    return runner.fetch_all(q)


def count_events(runner):
    q = SELECT(COUNT(events.c.id).AS("n")).FROM(events)
    return runner.fetch_one(q)


def list_event_bookings(runner, event_id: int, limit: int, offset: int):
    q = (
        SELECT(
            bookings.c.id.AS("id"),
            bookings.c.event_id.AS("event_id"),
            bookings.c.booking_code.AS("booking_code"),
            bookings.c.status.AS("status"),
            bookings.c.seats.AS("seats"),
            bookings.c.notes.AS("notes"),
            bookings.c.created_at.AS("created_at"),
            COUNT(attendees.c.id).AS("attendee_count"),
            MIN(attendees.c.full_name).AS("lead_name"),
            MIN(attendees.c.email).AS("lead_email"),
        )
        .FROM(bookings)
        .LEFT_JOIN(attendees, ON=attendees.c.booking_id == bookings.c.id)
        .WHERE(bookings.c.event_id == event_id)
        .GROUP_BY(bookings.c.id)
        .ORDER_BY(bookings.c.created_at.DESC())
        .LIMIT(limit)
        .OFFSET(offset)
    )
    return runner.fetch_all(q)


def count_event_bookings(runner, event_id: int):
    q = (
        SELECT(bookings.c.id.AS("id"))
        .FROM(bookings)
        .WHERE(bookings.c.event_id == event_id)
    )
    return runner.fetch_all(q)


def list_bookings(runner, term: Optional[str], status: Optional[str], limit: int, offset: int):
    predicates = []
    if status:
        predicates.append(bookings.c.status == status)
    if term:
        predicates.append(
            OR(
                attendees.c.full_name.contains(term),
                attendees.c.email.contains(term),
            )
        )

    q = (
        SELECT(
            bookings.c.id.AS("id"),
            bookings.c.event_id.AS("event_id"),
            bookings.c.booking_code.AS("booking_code"),
            bookings.c.status.AS("status"),
            bookings.c.seats.AS("seats"),
            bookings.c.notes.AS("notes"),
            bookings.c.created_at.AS("created_at"),
            events.c.title.AS("event_title"),
            events.c.starts_at.AS("starts_at"),
            COUNT(attendees.c.id).AS("attendee_count"),
            MIN(attendees.c.full_name).AS("lead_name"),
            MIN(attendees.c.email).AS("lead_email"),
        )
        .FROM(bookings)
        .JOIN(events, ON=events.c.id == bookings.c.event_id)
        .LEFT_JOIN(attendees, ON=attendees.c.booking_id == bookings.c.id)
        .GROUP_BY(bookings.c.id)
        .ORDER_BY(bookings.c.created_at.DESC())
        .LIMIT(limit)
        .OFFSET(offset)
    )
    if predicates:
        q = q.WHERE(*predicates)
    return runner.fetch_all(q)


def get_booking_row(runner, booking_id: int):
    q = (
        SELECT(
            bookings.c.id.AS("id"),
            bookings.c.event_id.AS("event_id"),
            bookings.c.booking_code.AS("booking_code"),
            bookings.c.status.AS("status"),
            bookings.c.seats.AS("seats"),
            bookings.c.notes.AS("notes"),
            bookings.c.created_at.AS("created_at"),
            events.c.title.AS("event_title"),
            events.c.starts_at.AS("starts_at"),
            COUNT(attendees.c.id).AS("attendee_count"),
            MIN(attendees.c.full_name).AS("lead_name"),
            MIN(attendees.c.email).AS("lead_email"),
        )
        .FROM(bookings)
        .JOIN(events, ON=events.c.id == bookings.c.event_id)
        .LEFT_JOIN(attendees, ON=attendees.c.booking_id == bookings.c.id)
        .WHERE(bookings.c.id == booking_id)
        .GROUP_BY(bookings.c.id)
        .LIMIT(1)
    )
    return runner.fetch_one(q)


def count_bookings(runner, term: Optional[str], status: Optional[str]):
    predicates = []
    if status:
        predicates.append(bookings.c.status == status)
    if term:
        predicates.append(
            OR(
                attendees.c.full_name.contains(term),
                attendees.c.email.contains(term),
            )
        )

    q = (
        SELECT(bookings.c.id.AS("id"))
        .FROM(bookings)
        .LEFT_JOIN(attendees, ON=attendees.c.booking_id == bookings.c.id)
        .GROUP_BY(bookings.c.id)
    )
    if predicates:
        q = q.WHERE(*predicates)
    return runner.fetch_all(q)


def get_booking_by_code(runner, booking_code: str):
    q = (
        SELECT(
            bookings.c.id.AS("id"),
            bookings.c.event_id.AS("event_id"),
            bookings.c.booking_code.AS("booking_code"),
            bookings.c.status.AS("status"),
            bookings.c.seats.AS("seats"),
            bookings.c.notes.AS("notes"),
            bookings.c.created_at.AS("created_at"),
        )
        .FROM(bookings)
        .WHERE(bookings.c.booking_code == booking_code)
        .LIMIT(1)
    )
    return runner.fetch_one(q)


def list_attendees_for_booking(runner, booking_id: int):
    q = using_pydantic(
        SELECT(
            attendees.c.id.AS("id"),
            attendees.c.booking_id.AS("booking_id"),
            attendees.c.full_name.AS("full_name"),
            attendees.c.email.AS("email"),
            attendees.c.phone.AS("phone"),
            attendees.c.created_at.AS("created_at"),
        )
        .FROM(attendees)
        .WHERE(attendees.c.booking_id == booking_id)
        .ORDER_BY(attendees.c.id.ASC())
    ).hydrate(AttendeeOut)
    return runner.fetch_all(q)


def seats_booked_for_event(runner, event_id: int) -> int:
    q = (
        SELECT(SUM(bookings.c.seats).AS("total"))
        .FROM(bookings)
        .WHERE(bookings.c.event_id == event_id, bookings.c.status != "canceled")
    )
    row = runner.fetch_one(q)
    if not row:
        return 0
    return int(row["total"] or 0)


def booking_code_exists(runner, booking_code: str) -> bool:
    q = (
        SELECT(bookings.c.id.AS("id"))
        .FROM(bookings)
        .WHERE(bookings.c.booking_code == booking_code)
        .LIMIT(1)
    )
    return runner.fetch_one(q) is not None


def create_booking(runner, event_id: int, booking_code: str, status: str, seats: int, notes: Optional[str]) -> int:
    now = datetime.utcnow().isoformat()
    result = runner.execute(
        INSERT(bookings).VALUES(
            event_id=event_id,
            booking_code=booking_code,
            status=status,
            seats=seats,
            notes=notes,
            created_at=now,
        )
    )
    return int(result.lastrowid)


def create_attendee(runner, booking_id: int, full_name: str, email: str, phone: Optional[str]) -> int:
    now = datetime.utcnow().isoformat()
    result = runner.execute(
        INSERT(attendees).VALUES(
            booking_id=booking_id,
            full_name=full_name,
            email=email,
            phone=phone,
            created_at=now,
        )
    )
    return int(result.lastrowid)


def update_booking_status(runner, booking_id: int, status: str) -> None:
    runner.execute(
        UPDATE(bookings)
        .SET(status=status)
        .WHERE(bookings.c.id == booking_id)
    )


def create_event(runner, data: dict) -> int:
    now = datetime.utcnow().isoformat()
    result = runner.execute(
        INSERT(events).VALUES(
            slug=data["slug"],
            title=data["title"],
            description=data.get("description"),
            location=data.get("location"),
            starts_at=data["starts_at"],
            ends_at=data["ends_at"],
            capacity=data["capacity"],
            price_cents=data["price_cents"],
            created_at=now,
        )
    )
    return int(result.lastrowid)


def update_event(runner, event_id: int, data: dict) -> None:
    runner.execute(
        UPDATE(events)
        .SET(
            slug=data["slug"],
            title=data["title"],
            description=data.get("description"),
            location=data.get("location"),
            starts_at=data["starts_at"],
            ends_at=data["ends_at"],
            capacity=data["capacity"],
            price_cents=data["price_cents"],
        )
        .WHERE(events.c.id == event_id)
    )


def staff_dashboard(runner):
    now_iso = datetime.utcnow().isoformat()
    total_events = runner.fetch_one(SELECT(COUNT(events.c.id).AS("n")).FROM(events))
    upcoming_events = runner.fetch_one(
        SELECT(COUNT(events.c.id).AS("n")).FROM(events).WHERE(events.c.starts_at >= now_iso)
    )
    total_bookings = runner.fetch_one(SELECT(COUNT(bookings.c.id).AS("n")).FROM(bookings))
    revenue_rows = runner.fetch_all(
        SELECT(bookings.c.seats.AS("seats"), events.c.price_cents.AS("price_cents"))
        .FROM(bookings)
        .JOIN(events, ON=events.c.id == bookings.c.event_id)
        .WHERE(bookings.c.status != "canceled")
    )
    revenue_total = sum(int(row["seats"]) * int(row["price_cents"]) for row in revenue_rows)
    bookings_by_status = runner.fetch_all(
        SELECT(bookings.c.status.AS("status"), COUNT(bookings.c.id).AS("n"))
        .FROM(bookings)
        .GROUP_BY(bookings.c.status)
        .ORDER_BY(bookings.c.status.ASC())
    )
    return {
        "total_events": int(total_events["n"]) if total_events else 0,
        "upcoming_events": int(upcoming_events["n"]) if upcoming_events else 0,
        "total_bookings": int(total_bookings["n"]) if total_bookings else 0,
        "revenue_cents": revenue_total,
        "bookings_by_status": bookings_by_status,
    }
