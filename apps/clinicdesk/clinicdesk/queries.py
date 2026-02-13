from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable, Optional

from sqlstratum import (
    SELECT,
    INSERT,
    UPDATE,
    DELETE,
    COUNT,
    SUM,
    AND,
    OR,
    Table,
    col,
)


patients = Table(
    "patients",
    col("id", int),
    col("full_name", str),
    col("phone", str),
    col("email", str),
    col("dob", str),
    col("created_at", str),
)

staff_users = Table(
    "staff_users",
    col("id", int),
    col("username", str),
    col("role", str),
    col("doctor_id", int),
    col("pin", str),
)

doctors = Table(
    "doctors",
    col("id", int),
    col("full_name", str),
    col("specialty", str),
    col("active", int),
)

services = Table(
    "services",
    col("id", int),
    col("name", str),
    col("duration_min", int),
    col("price_cents", int),
    col("active", int),
)

appointments = Table(
    "appointments",
    col("id", int),
    col("patient_id", int),
    col("doctor_id", int),
    col("service_id", int),
    col("starts_at", str),
    col("status", str),
    col("notes", str),
    col("created_at", str),
    col("updated_at", str),
)

invoices = Table(
    "invoices",
    col("id", int),
    col("appointment_id", int),
    col("patient_id", int),
    col("total_cents", int),
    col("status", str),
    col("created_at", str),
)

invoice_items = Table(
    "invoice_items",
    col("id", int),
    col("invoice_id", int),
    col("description", str),
    col("qty", int),
    col("unit_price_cents", int),
)


# Auth + user lookups

def get_patient_login(runner, email: str, dob: str):
    q = (
        SELECT(
            patients.c.id.AS("id"),
            patients.c.full_name.AS("full_name"),
            patients.c.email.AS("email"),
            patients.c.dob.AS("dob"),
        )
        .FROM(patients)
        .WHERE(patients.c.email == email, patients.c.dob == dob)
    )
    return runner.fetch_one(q)


def get_staff_login(runner, username: str, pin: str):
    q = (
        SELECT(
            staff_users.c.id.AS("id"),
            staff_users.c.username.AS("username"),
            staff_users.c.role.AS("role"),
            staff_users.c.doctor_id.AS("doctor_id"),
        )
        .FROM(staff_users)
        .WHERE(staff_users.c.username == username, staff_users.c.pin == pin)
    )
    return runner.fetch_one(q)


def get_patient_by_id(runner, patient_id: int):
    q = (
        SELECT(
            patients.c.id.AS("id"),
            patients.c.full_name.AS("full_name"),
            patients.c.phone.AS("phone"),
            patients.c.email.AS("email"),
            patients.c.dob.AS("dob"),
            patients.c.created_at.AS("created_at"),
        )
        .FROM(patients)
        .WHERE(patients.c.id == patient_id)
    )
    return runner.fetch_one(q)


def get_staff_user_by_id(runner, user_id: int):
    q = (
        SELECT(
            staff_users.c.id.AS("id"),
            staff_users.c.username.AS("username"),
            staff_users.c.role.AS("role"),
            staff_users.c.doctor_id.AS("doctor_id"),
        )
        .FROM(staff_users)
        .WHERE(staff_users.c.id == user_id)
    )
    return runner.fetch_one(q)


# Patient surface queries

def get_patient_upcoming(runner, patient_id: int, limit: int = 5):
    now_iso = datetime.utcnow().isoformat()
    q = (
        SELECT(
            appointments.c.id.AS("appointment_id"),
            appointments.c.starts_at.AS("starts_at"),
            appointments.c.status.AS("status"),
            doctors.c.full_name.AS("doctor_name"),
            services.c.name.AS("service_name"),
        )
        .FROM(appointments)
        .JOIN(doctors, ON=appointments.c.doctor_id == doctors.c.id)
        .JOIN(services, ON=appointments.c.service_id == services.c.id)
        .WHERE(appointments.c.patient_id == patient_id, appointments.c.starts_at >= now_iso)
        .ORDER_BY(appointments.c.starts_at.ASC())
        .LIMIT(limit)
    )
    return runner.fetch_all(q)


def get_patient_past(runner, patient_id: int, limit: int = 5):
    now_iso = datetime.utcnow().isoformat()
    q = (
        SELECT(
            appointments.c.id.AS("appointment_id"),
            appointments.c.starts_at.AS("starts_at"),
            appointments.c.status.AS("status"),
            doctors.c.full_name.AS("doctor_name"),
            services.c.name.AS("service_name"),
        )
        .FROM(appointments)
        .JOIN(doctors, ON=appointments.c.doctor_id == doctors.c.id)
        .JOIN(services, ON=appointments.c.service_id == services.c.id)
        .WHERE(appointments.c.patient_id == patient_id, appointments.c.starts_at < now_iso)
        .ORDER_BY(appointments.c.starts_at.DESC())
        .LIMIT(limit)
    )
    return runner.fetch_all(q)


def list_patient_appointments(
    runner,
    patient_id: int,
    status: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    limit: int,
    offset: int,
):
    predicates = [appointments.c.patient_id == patient_id]
    if status:
        predicates.append(appointments.c.status == status)
    if start_date:
        predicates.append(appointments.c.starts_at >= f"{start_date}T00:00:00")
    if end_date:
        predicates.append(appointments.c.starts_at <= f"{end_date}T23:59:59")

    q = (
        SELECT(
            appointments.c.id.AS("appointment_id"),
            appointments.c.starts_at.AS("starts_at"),
            appointments.c.status.AS("status"),
            appointments.c.notes.AS("notes"),
            doctors.c.full_name.AS("doctor_name"),
            services.c.name.AS("service_name"),
            services.c.price_cents.AS("service_price_cents"),
        )
        .FROM(appointments)
        .JOIN(doctors, ON=appointments.c.doctor_id == doctors.c.id)
        .JOIN(services, ON=appointments.c.service_id == services.c.id)
        .WHERE(*predicates)
        .ORDER_BY(appointments.c.starts_at.DESC())
        .LIMIT(limit)
        .OFFSET(offset)
    )
    return runner.fetch_all(q)


def count_patient_appointments(
    runner,
    patient_id: int,
    status: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
) -> int:
    predicates = [appointments.c.patient_id == patient_id]
    if status:
        predicates.append(appointments.c.status == status)
    if start_date:
        predicates.append(appointments.c.starts_at >= f"{start_date}T00:00:00")
    if end_date:
        predicates.append(appointments.c.starts_at <= f"{end_date}T23:59:59")

    q = (
        SELECT(COUNT(appointments.c.id).AS("n"))
        .FROM(appointments)
        .WHERE(*predicates)
    )
    row = runner.fetch_one(q)
    return int(row["n"]) if row else 0


def list_patient_invoice_summary(runner, patient_id: int, limit: int = 10):
    q = (
        SELECT(
            invoices.c.id.AS("invoice_id"),
            invoices.c.total_cents.AS("total_cents"),
            invoices.c.status.AS("status"),
            invoices.c.created_at.AS("created_at"),
            appointments.c.starts_at.AS("appointment_starts"),
        )
        .FROM(invoices)
        .JOIN(appointments, ON=invoices.c.appointment_id == appointments.c.id)
        .WHERE(invoices.c.patient_id == patient_id)
        .ORDER_BY(invoices.c.created_at.DESC())
        .LIMIT(limit)
    )
    return runner.fetch_all(q)


def list_active_services(runner):
    q = (
        SELECT(
            services.c.id.AS("id"),
            services.c.name.AS("name"),
            services.c.duration_min.AS("duration_min"),
            services.c.price_cents.AS("price_cents"),
        )
        .FROM(services)
        .WHERE(services.c.active == 1)
        .ORDER_BY(services.c.name.ASC())
    )
    return runner.fetch_all(q)


def list_active_doctors(runner):
    q = (
        SELECT(
            doctors.c.id.AS("id"),
            doctors.c.full_name.AS("full_name"),
            doctors.c.specialty.AS("specialty"),
        )
        .FROM(doctors)
        .WHERE(doctors.c.active == 1)
        .ORDER_BY(doctors.c.full_name.ASC())
    )
    return runner.fetch_all(q)


def list_doctor_appointments_on_day(runner, doctor_id: int, day: str):
    start = f"{day}T00:00:00"
    end = f"{day}T23:59:59"
    q = (
        SELECT(appointments.c.starts_at.AS("starts_at"))
        .FROM(appointments)
        .WHERE(
            appointments.c.doctor_id == doctor_id,
            appointments.c.starts_at >= start,
            appointments.c.starts_at <= end,
            appointments.c.status != "cancelled",
        )
    )
    return runner.fetch_all(q)


def create_appointment(
    runner,
    patient_id: int,
    doctor_id: int,
    service_id: int,
    starts_at: str,
    status: str,
    notes: str | None,
) -> int:
    now = datetime.utcnow().isoformat()
    result = runner.execute(
        INSERT(appointments).VALUES(
            patient_id=patient_id,
            doctor_id=doctor_id,
            service_id=service_id,
            starts_at=starts_at,
            status=status,
            notes=notes,
            created_at=now,
            updated_at=now,
        )
    )
    return int(result.lastrowid)


# Staff dashboard + patient search

def dashboard_kpis(runner):
    today = datetime.utcnow().date()
    start = datetime.combine(today, datetime.min.time()).isoformat()
    end = (datetime.combine(today, datetime.min.time()) + timedelta(days=1)).isoformat()

    appointments_today = runner.fetch_one(
        SELECT(COUNT(appointments.c.id).AS("n"))
        .FROM(appointments)
        .WHERE(appointments.c.starts_at >= start, appointments.c.starts_at < end)
    )

    requested_pending = runner.fetch_one(
        SELECT(COUNT(appointments.c.id).AS("n"))
        .FROM(appointments)
        .WHERE(appointments.c.status == "requested")
    )

    revenue_since = (datetime.utcnow() - timedelta(days=7)).isoformat()
    revenue = runner.fetch_one(
        SELECT(SUM(invoices.c.total_cents).AS("total"))
        .FROM(invoices)
        .WHERE(invoices.c.created_at >= revenue_since)
    )

    active_doctors = runner.fetch_one(
        SELECT(COUNT(doctors.c.id).AS("n"))
        .FROM(doctors)
        .WHERE(doctors.c.active == 1)
    )

    most_booked = runner.fetch_one(
        SELECT(
            services.c.name.AS("service_name"),
            COUNT(appointments.c.id).AS("n"),
        )
        .FROM(appointments)
        .JOIN(services, ON=appointments.c.service_id == services.c.id)
        .GROUP_BY(services.c.id)
        .ORDER_BY(COUNT(appointments.c.id).DESC())
        .LIMIT(1)
    )

    return {
        "appointments_today": int(appointments_today["n"]) if appointments_today else 0,
        "requested_pending": int(requested_pending["n"]) if requested_pending else 0,
        "revenue_last_7_days": int(revenue["total"] or 0) if revenue else 0,
        "active_doctors": int(active_doctors["n"]) if active_doctors else 0,
        "most_booked_service": most_booked,
    }


def search_patients(runner, term: str, limit: int, offset: int):
    if not term:
        q = (
            SELECT(
                patients.c.id.AS("id"),
                patients.c.full_name.AS("full_name"),
                patients.c.email.AS("email"),
                patients.c.phone.AS("phone"),
            )
            .FROM(patients)
            .ORDER_BY(patients.c.full_name.ASC())
            .LIMIT(limit)
            .OFFSET(offset)
        )
        return runner.fetch_all(q)

    predicate = OR(
        patients.c.full_name.contains(term),
        patients.c.email.contains(term),
        patients.c.phone.contains(term),
    )
    q = (
        SELECT(
            patients.c.id.AS("id"),
            patients.c.full_name.AS("full_name"),
            patients.c.email.AS("email"),
            patients.c.phone.AS("phone"),
        )
        .FROM(patients)
        .WHERE(predicate)
        .ORDER_BY(patients.c.full_name.ASC())
        .LIMIT(limit)
        .OFFSET(offset)
    )
    return runner.fetch_all(q)


def get_patient_detail_with_history(runner, patient_id: int, limit: int = 50):
    patient = get_patient_by_id(runner, patient_id)
    history = (
        SELECT(
            appointments.c.id.AS("appointment_id"),
            appointments.c.starts_at.AS("starts_at"),
            appointments.c.status.AS("status"),
            doctors.c.full_name.AS("doctor_name"),
            services.c.name.AS("service_name"),
        )
        .FROM(appointments)
        .JOIN(doctors, ON=appointments.c.doctor_id == doctors.c.id)
        .JOIN(services, ON=appointments.c.service_id == services.c.id)
        .WHERE(appointments.c.patient_id == patient_id)
        .ORDER_BY(appointments.c.starts_at.DESC())
        .LIMIT(limit)
    )
    return patient, runner.fetch_all(history)


# Staff appointments board

def list_staff_appointments(
    runner,
    status: Optional[str],
    doctor_id: Optional[int],
    start_date: Optional[str],
    end_date: Optional[str],
    limit: int,
    offset: int,
):
    predicates = []
    if status:
        predicates.append(appointments.c.status == status)
    if doctor_id:
        predicates.append(appointments.c.doctor_id == doctor_id)
    if start_date:
        predicates.append(appointments.c.starts_at >= f"{start_date}T00:00:00")
    if end_date:
        predicates.append(appointments.c.starts_at <= f"{end_date}T23:59:59")

    q = (
        SELECT(
            appointments.c.id.AS("appointment_id"),
            appointments.c.starts_at.AS("starts_at"),
            appointments.c.status.AS("status"),
            appointments.c.notes.AS("notes"),
            patients.c.full_name.AS("patient_name"),
            doctors.c.full_name.AS("doctor_name"),
            services.c.name.AS("service_name"),
        )
        .FROM(appointments)
        .JOIN(patients, ON=appointments.c.patient_id == patients.c.id)
        .JOIN(doctors, ON=appointments.c.doctor_id == doctors.c.id)
        .JOIN(services, ON=appointments.c.service_id == services.c.id)
    )

    if predicates:
        q = q.WHERE(*predicates)

    q = q.ORDER_BY(appointments.c.starts_at.DESC()).LIMIT(limit).OFFSET(offset)
    return runner.fetch_all(q)


def count_staff_appointments(
    runner,
    status: Optional[str],
    doctor_id: Optional[int],
    start_date: Optional[str],
    end_date: Optional[str],
) -> int:
    predicates = []
    if status:
        predicates.append(appointments.c.status == status)
    if doctor_id:
        predicates.append(appointments.c.doctor_id == doctor_id)
    if start_date:
        predicates.append(appointments.c.starts_at >= f"{start_date}T00:00:00")
    if end_date:
        predicates.append(appointments.c.starts_at <= f"{end_date}T23:59:59")

    q = SELECT(COUNT(appointments.c.id).AS("n")).FROM(appointments)
    if predicates:
        q = q.WHERE(*predicates)
    row = runner.fetch_one(q)
    return int(row["n"]) if row else 0


def get_appointment_detail(runner, appointment_id: int):
    q = (
        SELECT(
            appointments.c.id.AS("appointment_id"),
            appointments.c.starts_at.AS("starts_at"),
            appointments.c.status.AS("status"),
            appointments.c.notes.AS("notes"),
            appointments.c.patient_id.AS("patient_id"),
            appointments.c.doctor_id.AS("doctor_id"),
            appointments.c.service_id.AS("service_id"),
            patients.c.full_name.AS("patient_name"),
            doctors.c.full_name.AS("doctor_name"),
            services.c.name.AS("service_name"),
            services.c.price_cents.AS("service_price_cents"),
        )
        .FROM(appointments)
        .JOIN(patients, ON=appointments.c.patient_id == patients.c.id)
        .JOIN(doctors, ON=appointments.c.doctor_id == doctors.c.id)
        .JOIN(services, ON=appointments.c.service_id == services.c.id)
        .WHERE(appointments.c.id == appointment_id)
    )
    return runner.fetch_one(q)


def update_appointment_status(runner, appointment_id: int, status: str):
    now = datetime.utcnow().isoformat()
    return runner.execute(
        UPDATE(appointments)
        .SET(status=status, updated_at=now)
        .WHERE(appointments.c.id == appointment_id)
    )


def update_appointment_notes(runner, appointment_id: int, notes: str):
    now = datetime.utcnow().isoformat()
    return runner.execute(
        UPDATE(appointments)
        .SET(notes=notes, updated_at=now)
        .WHERE(appointments.c.id == appointment_id)
    )


def reschedule_appointment(runner, appointment_id: int, starts_at: str):
    now = datetime.utcnow().isoformat()
    return runner.execute(
        UPDATE(appointments)
        .SET(starts_at=starts_at, updated_at=now)
        .WHERE(appointments.c.id == appointment_id)
    )


# Doctor schedule

def list_doctor_schedule(
    runner,
    doctor_id: int,
    day: str,
    limit: int,
    offset: int,
):
    start = f"{day}T00:00:00"
    end = f"{day}T23:59:59"
    q = (
        SELECT(
            appointments.c.id.AS("appointment_id"),
            appointments.c.starts_at.AS("starts_at"),
            appointments.c.status.AS("status"),
            appointments.c.notes.AS("notes"),
            patients.c.full_name.AS("patient_name"),
            services.c.name.AS("service_name"),
        )
        .FROM(appointments)
        .JOIN(patients, ON=appointments.c.patient_id == patients.c.id)
        .JOIN(services, ON=appointments.c.service_id == services.c.id)
        .WHERE(
            appointments.c.doctor_id == doctor_id,
            appointments.c.starts_at >= start,
            appointments.c.starts_at <= end,
        )
        .ORDER_BY(appointments.c.starts_at.ASC())
        .LIMIT(limit)
        .OFFSET(offset)
    )
    return runner.fetch_all(q)


def count_doctor_schedule(runner, doctor_id: int, day: str) -> int:
    start = f"{day}T00:00:00"
    end = f"{day}T23:59:59"
    q = (
        SELECT(COUNT(appointments.c.id).AS("n"))
        .FROM(appointments)
        .WHERE(
            appointments.c.doctor_id == doctor_id,
            appointments.c.starts_at >= start,
            appointments.c.starts_at <= end,
        )
    )
    row = runner.fetch_one(q)
    return int(row["n"]) if row else 0


# Invoices

def list_invoices(runner, limit: int, offset: int):
    q = (
        SELECT(
            invoices.c.id.AS("invoice_id"),
            invoices.c.total_cents.AS("total_cents"),
            invoices.c.status.AS("status"),
            invoices.c.created_at.AS("created_at"),
            patients.c.full_name.AS("patient_name"),
            appointments.c.starts_at.AS("appointment_starts"),
        )
        .FROM(invoices)
        .JOIN(patients, ON=invoices.c.patient_id == patients.c.id)
        .JOIN(appointments, ON=invoices.c.appointment_id == appointments.c.id)
        .ORDER_BY(invoices.c.created_at.DESC())
        .LIMIT(limit)
        .OFFSET(offset)
    )
    return runner.fetch_all(q)


def get_invoice_by_id(runner, invoice_id: int):
    q = (
        SELECT(
            invoices.c.id.AS("invoice_id"),
            invoices.c.total_cents.AS("total_cents"),
            invoices.c.status.AS("status"),
            invoices.c.created_at.AS("created_at"),
            invoices.c.appointment_id.AS("appointment_id"),
            patients.c.full_name.AS("patient_name"),
            patients.c.email.AS("patient_email"),
        )
        .FROM(invoices)
        .JOIN(patients, ON=invoices.c.patient_id == patients.c.id)
        .WHERE(invoices.c.id == invoice_id)
    )
    return runner.fetch_one(q)


def get_invoice_by_appointment(runner, appointment_id: int):
    q = (
        SELECT(
            invoices.c.id.AS("invoice_id"),
            invoices.c.total_cents.AS("total_cents"),
            invoices.c.status.AS("status"),
        )
        .FROM(invoices)
        .WHERE(invoices.c.appointment_id == appointment_id)
    )
    return runner.fetch_one(q)


def list_invoice_items(runner, invoice_id: int):
    q = (
        SELECT(
            invoice_items.c.id.AS("item_id"),
            invoice_items.c.description.AS("description"),
            invoice_items.c.qty.AS("qty"),
            invoice_items.c.unit_price_cents.AS("unit_price_cents"),
        )
        .FROM(invoice_items)
        .WHERE(invoice_items.c.invoice_id == invoice_id)
        .ORDER_BY(invoice_items.c.id.ASC())
    )
    return runner.fetch_all(q)


def create_invoice(runner, appointment_id: int, patient_id: int, status: str):
    now = datetime.utcnow().isoformat()
    result = runner.execute(
        INSERT(invoices).VALUES(
            appointment_id=appointment_id,
            patient_id=patient_id,
            total_cents=0,
            status=status,
            created_at=now,
        )
    )
    return int(result.lastrowid)


def add_invoice_item(runner, invoice_id: int, description: str, qty: int, unit_price_cents: int):
    result = runner.execute(
        INSERT(invoice_items).VALUES(
            invoice_id=invoice_id,
            description=description,
            qty=qty,
            unit_price_cents=unit_price_cents,
        )
    )
    return int(result.lastrowid)


def delete_invoice_item(runner, item_id: int):
    return runner.execute(DELETE(invoice_items).WHERE(invoice_items.c.id == item_id))


def update_invoice_total(runner, invoice_id: int):
    items = list_invoice_items(runner, invoice_id)
    total = sum(int(item["qty"]) * int(item["unit_price_cents"]) for item in items)
    runner.execute(
        UPDATE(invoices)
        .SET(total_cents=total)
        .WHERE(invoices.c.id == invoice_id)
    )
    return total


# Utilities

def to_iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def parse_ids(values: Iterable[str]) -> list[int]:
    out = []
    for value in values:
        try:
            out.append(int(value))
        except ValueError:
            continue
    return out
