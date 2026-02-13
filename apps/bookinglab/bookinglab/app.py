from __future__ import annotations

import logging
import os
import random
import string
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote

from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from pydantic import ValidationError
from sqlstratum.hydrate.pydantic import hydrate_model

from bookinglab.auth import get_session_user, login_user, logout_user, require_role
from bookinglab.config import BASE_DIR, Config
from bookinglab.db import get_runner, init_db
from bookinglab import queries
from bookinglab.models import (
    BookingCreate,
    BookingOut,
    BookingStatus,
    EventCreate,
    EventOut,
)


def configure_logging() -> None:
    debug_flag = os.environ.get("SQLSTRATUM_DEBUG", "").lower()
    if debug_flag in {"1", "true", "yes"}:
        logging.basicConfig(level=logging.DEBUG)
        logging.getLogger("sqlstratum").setLevel(logging.DEBUG)


configure_logging()

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=Config.SECRET_KEY, same_site="lax")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.on_event("startup")
def _startup() -> None:
    init_db()


def get_runner_dep():
    runner = get_runner()
    try:
        yield runner
    finally:
        runner.connection.close()


def render(request: Request, template_name: str, **context):
    return templates.TemplateResponse(
        template_name,
        {
            "request": request,
            "current_user": get_session_user(request),
            **context,
        },
    )


def _enrich_event(event: Optional[EventOut]) -> Optional[EventOut]:
    if event is None:
        return None
    seats_booked = int(event.seats_booked or 0)
    revenue_cents = seats_booked * int(event.price_cents or 0)
    remaining_capacity = max(int(event.capacity) - seats_booked, 0)
    return event.model_copy(
        update={
            "seats_booked": seats_booked,
            "revenue_cents": revenue_cents,
            "remaining_capacity": remaining_capacity,
        }
    )


def _generate_booking_code() -> str:
    return "BK" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def _get_unique_booking_code(runner) -> str:
    for _ in range(20):
        code = _generate_booking_code()
        if not queries.booking_code_exists(runner, code):
            return code
    raise RuntimeError("Unable to allocate booking code")


@app.get("/", response_class=HTMLResponse)
def index(request: Request, runner=Depends(get_runner_dep)):
    rows = queries.list_upcoming_events(runner, limit=30)
    events = [e for e in (_enrich_event(row) for row in rows) if e is not None]
    return render(request, "public/index.html", events=events)


@app.get("/events/{slug}", response_class=HTMLResponse)
def event_detail(slug: str, request: Request, runner=Depends(get_runner_dep)):
    row = queries.get_event_by_slug(runner, slug)
    event = _enrich_event(row)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return render(request, "public/event_detail.html", event=event)


@app.post("/events/{slug}/book")
async def book_event(slug: str, request: Request, runner=Depends(get_runner_dep)):
    row = queries.get_event_by_slug(runner, slug)
    event = _enrich_event(row)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    form = await request.form()
    seats_raw = form.get("seats", "1")
    form_data = {
        "full_name": form.get("full_name", "").strip(),
        "email": form.get("email", "").strip(),
        "phone": form.get("phone", "").strip() or None,
        "seats": seats_raw,
        "notes": form.get("notes") or None,
    }
    payload = {
        "event_id": event.id,
        "seats": int(seats_raw) if str(seats_raw).isdigit() else seats_raw,
        "notes": form_data["notes"],
        "attendees": [
            {
                "full_name": form_data["full_name"],
                "email": form_data["email"],
                "phone": form_data["phone"],
            }
        ],
    }

    try:
        booking_in = BookingCreate.model_validate(payload)
    except ValidationError as exc:
        return render(
            request,
            "public/event_detail.html",
            event=event,
            error="; ".join(err["msg"] for err in exc.errors()),
            form_data=form_data,
        )

    now = datetime.now(timezone.utc)
    if event.starts_at <= now:
        return render(
            request,
            "public/event_detail.html",
            event=event,
            error="This event already started or ended.",
            form_data=form_data,
        )

    with runner.transaction():
        seats_booked = queries.seats_booked_for_event(runner, event.id)
        remaining = event.capacity - seats_booked
        if booking_in.seats > remaining:
            return render(
                request,
                "public/event_detail.html",
                event=event,
                error=f"Only {remaining} seats remain for this event.",
                form_data=form_data,
            )

        booking_code = _get_unique_booking_code(runner)
        booking_id = queries.create_booking(
            runner,
            event_id=event.id,
            booking_code=booking_code,
            status=BookingStatus.requested.value,
            seats=booking_in.seats,
            notes=booking_in.notes,
        )
        for attendee in booking_in.attendees:
            queries.create_attendee(
                runner,
                booking_id=booking_id,
                full_name=attendee.full_name,
                email=attendee.email,
                phone=attendee.phone,
            )

    return RedirectResponse(url=f"/booking/{booking_code}", status_code=303)


@app.get("/booking/{booking_code}", response_class=HTMLResponse)
def booking_confirmation(booking_code: str, request: Request, runner=Depends(get_runner_dep)):
    booking_row = queries.get_booking_by_code(runner, booking_code)
    if booking_row is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    event_row = queries.get_event_by_id(runner, int(booking_row["event_id"]))
    attendees = queries.list_attendees_for_booking(runner, int(booking_row["id"]))
    event = _enrich_event(event_row)

    data = dict(booking_row)
    data["event"] = event.model_dump() if event else None
    data["attendees"] = [attendee.model_dump() for attendee in attendees]
    booking = hydrate_model(BookingOut, data)
    return render(request, "public/booking_confirm.html", booking=booking)


@app.get("/staff/login", response_class=HTMLResponse)
def staff_login(request: Request):
    return render(request, "staff/login.html")


@app.post("/staff/login")
async def staff_login_submit(request: Request, runner=Depends(get_runner_dep)):
    form = await request.form()
    username = form.get("username", "").strip()
    pin = form.get("pin", "").strip()
    next_url = form.get("next") or "/staff"

    staff_user = queries.get_staff_login(runner, username, pin)
    if staff_user:
        login_user(request, int(staff_user["id"]), staff_user["role"], staff_user["display_name"])
        return RedirectResponse(url=next_url, status_code=303)

    return render(request, "staff/login.html", error="Invalid credentials.")


@app.get("/staff/logout")
def staff_logout(request: Request):
    logout_user(request)
    return RedirectResponse(url="/staff/login", status_code=303)


@app.get("/staff", response_class=HTMLResponse)
def staff_dashboard(request: Request, runner=Depends(get_runner_dep)):
    user = require_role(request, "staff", "admin")
    if not user:
        return RedirectResponse(url=f"/staff/login?next={quote(request.url.path)}", status_code=303)
    kpis = queries.staff_dashboard(runner)
    return render(request, "staff/dashboard.html", kpis=kpis)


@app.get("/staff/events", response_class=HTMLResponse)
def staff_events(request: Request, page: int = 1, runner=Depends(get_runner_dep)):
    user = require_role(request, "staff", "admin")
    if not user:
        return RedirectResponse(url=f"/staff/login?next={quote(request.url.path)}", status_code=303)

    per_page = Config.ITEMS_PER_PAGE
    offset = (page - 1) * per_page
    rows = queries.list_events(runner, per_page, offset)
    events = [e for e in (_enrich_event(row) for row in rows) if e is not None]
    total_rows = queries.count_events(runner)
    total = int(total_rows["n"]) if total_rows else 0
    return render(
        request,
        "staff/events.html",
        events=events,
        page=page,
        per_page=per_page,
        total=total,
    )


@app.get("/staff/events/new", response_class=HTMLResponse)
def staff_event_new(request: Request):
    user = require_role(request, "staff", "admin")
    if not user:
        return RedirectResponse(url=f"/staff/login?next={quote(request.url.path)}", status_code=303)
    return render(request, "staff/event_form.html", mode="new")


def _slugify(value: str) -> str:
    import re

    slug = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "event"


def _event_payload_from_form(form) -> dict:
    return {
        "slug": form.get("slug") or "",
        "title": form.get("title") or "",
        "description": form.get("description") or None,
        "location": form.get("location") or None,
        "starts_at": form.get("starts_at") or "",
        "ends_at": form.get("ends_at") or "",
        "capacity": int(form.get("capacity", "0") or 0),
        "price_cents": int(form.get("price_cents", "0") or 0),
    }


def _event_data_for_insert(event_in: EventCreate) -> dict:
    data = event_in.model_dump()
    data["starts_at"] = event_in.starts_at.isoformat()
    data["ends_at"] = event_in.ends_at.isoformat()
    return data


@app.post("/staff/events/new")
async def staff_event_create(request: Request, runner=Depends(get_runner_dep)):
    user = require_role(request, "staff", "admin")
    if not user:
        return RedirectResponse(url=f"/staff/login?next={quote(request.url.path)}", status_code=303)

    form = await request.form()
    payload = _event_payload_from_form(form)
    if not payload["slug"]:
        payload["slug"] = _slugify(payload["title"])

    try:
        event_in = EventCreate.model_validate(payload)
    except ValidationError as exc:
        return render(
            request,
            "staff/event_form.html",
            mode="new",
            error="; ".join(err["msg"] for err in exc.errors()),
            form_data=payload,
        )

    queries.create_event(runner, _event_data_for_insert(event_in))
    return RedirectResponse(url="/staff/events", status_code=303)


@app.get("/staff/events/{event_id}", response_class=HTMLResponse)
def staff_event_detail(event_id: int, request: Request, page: int = 1, runner=Depends(get_runner_dep)):
    user = require_role(request, "staff", "admin")
    if not user:
        return RedirectResponse(url=f"/staff/login?next={quote(request.url.path)}", status_code=303)

    event_row = queries.get_event_by_id(runner, event_id)
    event = _enrich_event(event_row)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    per_page = Config.ITEMS_PER_PAGE
    offset = (page - 1) * per_page
    booking_rows = queries.list_event_bookings(runner, event_id, per_page, offset)
    total = len(queries.count_event_bookings(runner, event_id))

    return render(
        request,
        "staff/event_detail.html",
        event=event,
        bookings=booking_rows,
        total=total,
        page=page,
        per_page=per_page,
    )


@app.get("/staff/events/{event_id}/edit", response_class=HTMLResponse)
def staff_event_edit(event_id: int, request: Request, runner=Depends(get_runner_dep)):
    user = require_role(request, "staff", "admin")
    if not user:
        return RedirectResponse(url=f"/staff/login?next={quote(request.url.path)}", status_code=303)

    event_row = queries.get_event_by_id(runner, event_id)
    event = _enrich_event(event_row)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    form_data = {
        "slug": event.slug,
        "title": event.title,
        "description": event.description,
        "location": event.location,
        "starts_at": event.starts_at.isoformat(timespec="minutes"),
        "ends_at": event.ends_at.isoformat(timespec="minutes"),
        "capacity": event.capacity,
        "price_cents": event.price_cents,
    }
    return render(request, "staff/event_form.html", mode="edit", event=event, form_data=form_data)


@app.post("/staff/events/{event_id}/edit")
async def staff_event_update(event_id: int, request: Request, runner=Depends(get_runner_dep)):
    user = require_role(request, "staff", "admin")
    if not user:
        return RedirectResponse(url=f"/staff/login?next={quote(request.url.path)}", status_code=303)

    form = await request.form()
    payload = _event_payload_from_form(form)
    if not payload["slug"]:
        payload["slug"] = _slugify(payload["title"])

    try:
        event_in = EventCreate.model_validate(payload)
    except ValidationError as exc:
        return render(
            request,
            "staff/event_form.html",
            mode="edit",
            error="; ".join(err["msg"] for err in exc.errors()),
            form_data=payload,
            event={"id": event_id},
        )

    queries.update_event(runner, event_id, _event_data_for_insert(event_in))
    return RedirectResponse(url=f"/staff/events/{event_id}", status_code=303)


@app.get("/staff/bookings", response_class=HTMLResponse)
def staff_bookings(request: Request, page: int = 1, runner=Depends(get_runner_dep)):
    user = require_role(request, "staff", "admin")
    if not user:
        return RedirectResponse(url=f"/staff/login?next={quote(request.url.path)}", status_code=303)

    term = request.query_params.get("q") or None
    status = request.query_params.get("status") or None
    per_page = Config.ITEMS_PER_PAGE
    offset = (page - 1) * per_page

    rows = queries.list_bookings(runner, term, status, per_page, offset)
    total = len(queries.count_bookings(runner, term, status))

    return render(
        request,
        "staff/bookings.html",
        bookings=rows,
        total=total,
        page=page,
        per_page=per_page,
        term=term or "",
        status=status or "",
    )


@app.get("/staff/bookings/list", response_class=HTMLResponse)
def staff_bookings_list(request: Request, page: int = 1, runner=Depends(get_runner_dep)):
    user = require_role(request, "staff", "admin")
    if not user:
        return RedirectResponse(url=f"/staff/login?next={quote(request.url.path)}", status_code=303)

    term = request.query_params.get("q") or None
    status = request.query_params.get("status") or None
    per_page = Config.ITEMS_PER_PAGE
    offset = (page - 1) * per_page

    rows = queries.list_bookings(runner, term, status, per_page, offset)
    total = len(queries.count_bookings(runner, term, status))

    return render(
        request,
        "partials/bookings_table.html",
        bookings=rows,
        total=total,
        page=page,
        per_page=per_page,
        term=term or "",
        status=status or "",
    )


@app.post("/staff/bookings/{booking_id}/status", response_class=HTMLResponse)
async def staff_booking_update_status(booking_id: int, request: Request, runner=Depends(get_runner_dep)):
    user = require_role(request, "staff", "admin")
    if not user:
        return RedirectResponse(url=f"/staff/login?next={quote(request.url.path)}", status_code=303)

    form = await request.form()
    status = form.get("status") or BookingStatus.requested.value
    queries.update_booking_status(runner, booking_id, status)

    row = queries.get_booking_row(runner, booking_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Booking not found")

    return render(request, "partials/booking_row.html", booking=row)
