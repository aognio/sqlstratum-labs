from __future__ import annotations

from datetime import datetime, timedelta
from flask import Blueprint, current_app, render_template, request, redirect, url_for, g

from clinicdesk.auth import require_role
from clinicdesk.db import get_runner
from clinicdesk import queries


bp = Blueprint("patient", __name__, url_prefix="/patient")


def _is_htmx() -> bool:
    return request.headers.get("HX-Request") == "true"


@bp.route("/")
@bp.route("/home")
@require_role("patient")
def home():
    runner = get_runner()
    patient_id = g.current_user["id"]
    profile = queries.get_patient_by_id(runner, patient_id)
    upcoming = queries.get_patient_upcoming(runner, patient_id, limit=5)
    past = queries.get_patient_past(runner, patient_id, limit=5)
    invoices = queries.list_patient_invoice_summary(runner, patient_id, limit=8)
    return render_template(
        "patient/home.html",
        profile=profile,
        upcoming=upcoming,
        past=past,
        invoices=invoices,
    )


@bp.route("/appointments")
@require_role("patient")
def appointments():
    runner = get_runner()
    services = queries.list_active_services(runner)
    return render_template(
        "patient/appointments.html",
        services=services,
    )


@bp.route("/appointments/list")
@require_role("patient")
def appointments_list():
    runner = get_runner()
    patient_id = g.current_user["id"]
    status = request.args.get("status") or None
    start_date = request.args.get("start_date") or None
    end_date = request.args.get("end_date") or None
    page = int(request.args.get("page", "1"))
    per_page = current_app.config["ITEMS_PER_PAGE"]
    offset = (page - 1) * per_page

    items = queries.list_patient_appointments(
        runner,
        patient_id,
        status,
        start_date,
        end_date,
        per_page,
        offset,
    )
    total = queries.count_patient_appointments(runner, patient_id, status, start_date, end_date)
    return render_template(
        "patient/_appointments_table.html",
        items=items,
        total=total,
        page=page,
        per_page=per_page,
    )


@bp.route("/request")
@require_role("patient")
def request_appointment():
    runner = get_runner()
    services = queries.list_active_services(runner)
    doctors = queries.list_active_doctors(runner)
    return render_template(
        "patient/request.html",
        services=services,
        doctors=doctors,
    )


@bp.route("/request/slots")
@require_role("patient")
def request_slots():
    runner = get_runner()
    service_id = request.args.get("service_id")
    doctor_id = request.args.get("doctor_id")
    day = request.args.get("day")
    if not (service_id and day):
        return render_template("patient/_slots.html", slots=[], day=day)

    services = {s["id"]: s for s in queries.list_active_services(runner)}
    service = services.get(int(service_id))
    duration = service["duration_min"] if service else 30

    slot_times = []
    start = datetime.fromisoformat(f"{day}T09:00:00")
    end = datetime.fromisoformat(f"{day}T17:00:00")
    current = start
    while current <= end:
        slot_times.append(current)
        current += timedelta(minutes=duration)

    slots = []
    doctors = queries.list_active_doctors(runner)
    if doctor_id and doctor_id != "any":
        doctor_id_int = int(doctor_id)
        booked = {row["starts_at"] for row in queries.list_doctor_appointments_on_day(runner, doctor_id_int, day)}
        for slot in slot_times:
            if slot.isoformat() in booked:
                continue
            slots.append({"doctor_id": doctor_id_int, "doctor_name": next(d["full_name"] for d in doctors if d["id"] == doctor_id_int), "starts_at": slot.isoformat()})
    else:
        booked_by_doctor = {}
        for doc in doctors:
            booked_by_doctor[doc["id"]] = {row["starts_at"] for row in queries.list_doctor_appointments_on_day(runner, doc["id"], day)}
        for slot in slot_times:
            for doc in doctors:
                if slot.isoformat() in booked_by_doctor[doc["id"]]:
                    continue
                slots.append({"doctor_id": doc["id"], "doctor_name": doc["full_name"], "starts_at": slot.isoformat()})

    return render_template("patient/_slots.html", slots=slots, day=day, service_id=service_id)


@bp.route("/request/book", methods=["POST"])
@require_role("patient")
def book_appointment():
    runner = get_runner()
    patient_id = g.current_user["id"]
    service_id = int(request.form.get("service_id", "0"))
    doctor_id = int(request.form.get("doctor_id", "0"))
    starts_at = request.form.get("starts_at")
    if not (service_id and doctor_id and starts_at):
        return render_template("patient/_book_result.html", ok=False, message="Missing required fields."), 400

    appointment_id = queries.create_appointment(
        runner,
        patient_id=patient_id,
        doctor_id=doctor_id,
        service_id=service_id,
        starts_at=starts_at,
        status="requested",
        notes=None,
    )

    if _is_htmx():
        return render_template("patient/_book_result.html", ok=True, message=f"Request submitted. Appointment #{appointment_id}.")
    return redirect(url_for("patient.home"))
