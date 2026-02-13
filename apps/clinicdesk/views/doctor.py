from __future__ import annotations

from datetime import date

from flask import Blueprint, current_app, render_template, request, redirect, url_for, g

from clinicdesk.auth import require_role
from clinicdesk.db import get_runner
from clinicdesk import queries


bp = Blueprint("doctor", __name__, url_prefix="/doctor")


def _is_htmx() -> bool:
    return request.headers.get("HX-Request") == "true"


@bp.route("/")
@bp.route("/schedule")
@require_role("doctor")
def schedule():
    runner = get_runner()
    user = g.current_user
    staff_user = queries.get_staff_user_by_id(runner, user["id"])
    doctor_id = staff_user["doctor_id"]
    day = request.args.get("day") or date.today().isoformat()
    page = int(request.args.get("page", "1"))
    per_page = current_app.config["ITEMS_PER_PAGE"]
    offset = (page - 1) * per_page

    items = queries.list_doctor_schedule(runner, doctor_id, day, per_page, offset)
    total = queries.count_doctor_schedule(runner, doctor_id, day)
    return render_template("doctor/schedule.html", items=items, total=total, day=day, page=page, per_page=per_page)


@bp.route("/appointments/<int:appointment_id>/status", methods=["POST"])
@require_role("doctor")
def update_status(appointment_id: int):
    runner = get_runner()
    status = request.form.get("status")
    if not status:
        return "Missing status", 400
    queries.update_appointment_status(runner, appointment_id, status)
    detail = queries.get_appointment_detail(runner, appointment_id)
    if _is_htmx():
        return render_template("doctor/_schedule_row.html", item=detail)
    return redirect(url_for("doctor.schedule"))


@bp.route("/appointments/<int:appointment_id>/notes", methods=["POST"])
@require_role("doctor")
def update_notes(appointment_id: int):
    runner = get_runner()
    notes = request.form.get("notes", "")
    queries.update_appointment_notes(runner, appointment_id, notes)
    detail = queries.get_appointment_detail(runner, appointment_id)
    if _is_htmx():
        return render_template("doctor/_schedule_row.html", item=detail)
    return redirect(url_for("doctor.schedule"))
