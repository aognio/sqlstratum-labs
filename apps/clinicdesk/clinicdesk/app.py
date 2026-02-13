from __future__ import annotations

import logging
from flask import Flask, render_template, request, redirect, url_for
from dotenv import load_dotenv

from clinicdesk.config import Config
from clinicdesk.db import init_app, get_runner
from clinicdesk.auth import login_user, logout_user, get_session_user
from clinicdesk.views import patient as patient_views
from clinicdesk.views import staff as staff_views
from clinicdesk.views import doctor as doctor_views
from clinicdesk import queries


load_dotenv()


def create_app() -> Flask:
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger("sqlstratum").setLevel(logging.DEBUG)
    sql_logger = logging.getLogger("sqlstratum")
    if not any(isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", "").endswith("sql.log") for h in sql_logger.handlers):
        file_handler = logging.FileHandler("sql.log")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s: %(message)s"))
        sql_logger.addHandler(file_handler)

    app = Flask(__name__)
    app.config.from_object(Config)

    init_app(app)

    app.register_blueprint(patient_views.bp)
    app.register_blueprint(staff_views.bp)
    app.register_blueprint(doctor_views.bp)

    @app.context_processor
    def inject_user():
        return {"current_user": get_session_user()}

    @app.route("/")
    def index():
        user = get_session_user()
        if not user:
            return redirect(url_for("login"))
        if user["role"] == "patient":
            return redirect(url_for("patient.home"))
        if user["role"] == "doctor":
            return redirect(url_for("doctor.schedule"))
        return redirect(url_for("staff.dashboard"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            mode = request.form.get("mode")
            runner = get_runner()
            if mode == "patient":
                email = request.form.get("email", "").strip()
                dob = request.form.get("dob", "").strip()
                patient = queries.get_patient_login(runner, email, dob)
                if patient:
                    login_user(patient["id"], "patient", patient["full_name"])
                    return redirect(url_for("patient.home"))
            elif mode == "staff":
                username = request.form.get("username", "").strip()
                pin = request.form.get("pin", "").strip()
                staff_user = queries.get_staff_login(runner, username, pin)
                if staff_user:
                    role = staff_user["role"]
                    login_user(staff_user["id"], role, staff_user["username"])
                    if role == "doctor":
                        return redirect(url_for("doctor.schedule"))
                    return redirect(url_for("staff.dashboard"))
            return render_template("login.html", error="Invalid credentials.")
        return render_template("login.html")

    @app.route("/logout")
    def logout():
        logout_user()
        return redirect(url_for("login"))

    return app


app = create_app()
