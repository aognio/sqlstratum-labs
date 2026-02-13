from __future__ import annotations

from flask import Blueprint, current_app, render_template, request, redirect, url_for, g

from clinicdesk.auth import require_role
from clinicdesk.db import get_runner
from clinicdesk import queries


bp = Blueprint("staff", __name__, url_prefix="/staff")


def _is_htmx() -> bool:
    return request.headers.get("HX-Request") == "true"


@bp.route("/")
@bp.route("/dashboard")
@require_role("staff", "doctor")
def dashboard():
    runner = get_runner()
    kpis = queries.dashboard_kpis(runner)
    return render_template("staff/dashboard.html", kpis=kpis)


@bp.route("/patients")
@require_role("staff")
def patients():
    return render_template("staff/patients.html")


@bp.route("/patients/search")
@require_role("staff")
def patients_search():
    runner = get_runner()
    term = request.args.get("q", "").strip()
    page = int(request.args.get("page", "1"))
    per_page = current_app.config["ITEMS_PER_PAGE"]
    offset = (page - 1) * per_page
    results = queries.search_patients(runner, term, per_page, offset)
    return render_template("staff/_patients_results.html", results=results, term=term, page=page, per_page=per_page)


@bp.route("/patients/<int:patient_id>")
@require_role("staff")
def patient_detail(patient_id: int):
    runner = get_runner()
    patient, history = queries.get_patient_detail_with_history(runner, patient_id)
    return render_template("staff/patient_detail.html", patient=patient, history=history)


@bp.route("/appointments")
@require_role("staff")
def appointments():
    runner = get_runner()
    doctors = queries.list_active_doctors(runner)
    services = queries.list_active_services(runner)
    return render_template("staff/appointments.html", doctors=doctors, services=services)


@bp.route("/appointments/list")
@require_role("staff")
def appointments_list():
    runner = get_runner()
    status = request.args.get("status") or None
    doctor_id = request.args.get("doctor_id")
    doctor_id = int(doctor_id) if doctor_id else None
    start_date = request.args.get("start_date") or None
    end_date = request.args.get("end_date") or None
    page = int(request.args.get("page", "1"))
    per_page = current_app.config["ITEMS_PER_PAGE"]
    offset = (page - 1) * per_page

    items = queries.list_staff_appointments(runner, status, doctor_id, start_date, end_date, per_page, offset)
    total = queries.count_staff_appointments(runner, status, doctor_id, start_date, end_date)
    return render_template(
        "staff/_appointments_table.html",
        items=items,
        total=total,
        page=page,
        per_page=per_page,
    )


@bp.route("/appointments/create", methods=["POST"])
@require_role("staff")
def create_appointment():
    runner = get_runner()
    patient_id = int(request.form.get("patient_id", "0"))
    doctor_id = int(request.form.get("doctor_id", "0"))
    service_id = int(request.form.get("service_id", "0"))
    starts_at = request.form.get("starts_at")
    status = request.form.get("status", "confirmed")
    if not (patient_id and doctor_id and service_id and starts_at):
        return "Missing required fields", 400
    if len(starts_at) == 16:
        starts_at = f"{starts_at}:00"
    with runner.transaction():
        appointment_id = queries.create_appointment(
            runner,
            patient_id=patient_id,
            doctor_id=doctor_id,
            service_id=service_id,
            starts_at=starts_at,
            status=status,
            notes=None,
        )
    detail = queries.get_appointment_detail(runner, appointment_id)
    if _is_htmx():
        return render_template("staff/_appointments_row.html", item=detail)
    return redirect(url_for("staff.appointments"))


@bp.route("/appointments/<int:appointment_id>/confirm", methods=["POST"])
@require_role("staff")
def confirm_appointment(appointment_id: int):
    runner = get_runner()
    queries.update_appointment_status(runner, appointment_id, "confirmed")
    detail = queries.get_appointment_detail(runner, appointment_id)
    if _is_htmx():
        return render_template("staff/_appointments_row.html", item=detail)
    return redirect(url_for("staff.appointments"))


@bp.route("/appointments/<int:appointment_id>/cancel", methods=["POST"])
@require_role("staff")
def cancel_appointment(appointment_id: int):
    runner = get_runner()
    queries.update_appointment_status(runner, appointment_id, "cancelled")
    detail = queries.get_appointment_detail(runner, appointment_id)
    if _is_htmx():
        return render_template("staff/_appointments_row.html", item=detail)
    return redirect(url_for("staff.appointments"))


@bp.route("/appointments/<int:appointment_id>/reschedule", methods=["POST"])
@require_role("staff")
def reschedule_appointment(appointment_id: int):
    runner = get_runner()
    starts_at = request.form.get("starts_at")
    if not starts_at:
        return "Missing starts_at", 400
    if len(starts_at) == 16:
        starts_at = f"{starts_at}:00"
    with runner.transaction():
        queries.reschedule_appointment(runner, appointment_id, starts_at)
    detail = queries.get_appointment_detail(runner, appointment_id)
    if _is_htmx():
        return render_template("staff/_appointments_row.html", item=detail)
    return redirect(url_for("staff.appointments"))


@bp.route("/invoices")
@require_role("staff")
def invoices():
    runner = get_runner()
    page = int(request.args.get("page", "1"))
    per_page = current_app.config["ITEMS_PER_PAGE"]
    offset = (page - 1) * per_page
    items = queries.list_invoices(runner, per_page, offset)
    return render_template("staff/invoices.html", items=items, page=page, per_page=per_page)


@bp.route("/invoices/<int:invoice_id>")
@require_role("staff")
def invoice_detail(invoice_id: int):
    runner = get_runner()
    invoice = queries.get_invoice_by_id(runner, invoice_id)
    items = queries.list_invoice_items(runner, invoice_id)
    return render_template("staff/invoice_detail.html", invoice=invoice, items=items)


@bp.route("/invoices/generate/<int:appointment_id>", methods=["POST"])
@require_role("staff")
def generate_invoice(appointment_id: int):
    runner = get_runner()
    appointment = queries.get_appointment_detail(runner, appointment_id)
    if appointment is None:
        return "Not found", 404

    existing = queries.get_invoice_by_appointment(runner, appointment_id)
    if existing:
        if _is_htmx():
            return render_template("staff/_invoice_badge.html", invoice=existing)
        return redirect(url_for("staff.invoice_detail", invoice_id=existing["invoice_id"]))

    with runner.transaction():
        invoice_id = queries.create_invoice(
            runner,
            appointment_id=appointment_id,
            patient_id=appointment["patient_id"],
            status="draft",
        )
        queries.add_invoice_item(
            runner,
            invoice_id=invoice_id,
            description=f"{appointment['service_name']} service",
            qty=1,
            unit_price_cents=appointment["service_price_cents"],
        )
        queries.update_invoice_total(runner, invoice_id)

    invoice = queries.get_invoice_by_id(runner, invoice_id)
    if _is_htmx():
        return render_template("staff/_invoice_badge.html", invoice=invoice)
    return redirect(url_for("staff.invoice_detail", invoice_id=invoice_id))


@bp.route("/invoices/<int:invoice_id>/items/add", methods=["POST"])
@require_role("staff")
def add_invoice_item(invoice_id: int):
    runner = get_runner()
    description = request.form.get("description", "").strip()
    qty = int(request.form.get("qty", "1"))
    unit_price_cents = int(request.form.get("unit_price_cents", "0"))
    if not description:
        return "Missing description", 400

    with runner.transaction():
        queries.add_invoice_item(runner, invoice_id, description, qty, unit_price_cents)
        queries.update_invoice_total(runner, invoice_id)

    items = queries.list_invoice_items(runner, invoice_id)
    invoice = queries.get_invoice_by_id(runner, invoice_id)
    if _is_htmx():
        return render_template("staff/_invoice_items.html", items=items, invoice=invoice)
    return redirect(url_for("staff.invoice_detail", invoice_id=invoice_id))


@bp.route("/invoices/<int:invoice_id>/items/<int:item_id>/delete", methods=["POST"])
@require_role("staff")
def delete_invoice_item(invoice_id: int, item_id: int):
    runner = get_runner()
    with runner.transaction():
        queries.delete_invoice_item(runner, item_id)
        queries.update_invoice_total(runner, invoice_id)

    items = queries.list_invoice_items(runner, invoice_id)
    invoice = queries.get_invoice_by_id(runner, invoice_id)
    if _is_htmx():
        return render_template("staff/_invoice_items.html", items=items, invoice=invoice)
    return redirect(url_for("staff.invoice_detail", invoice_id=invoice_id))
