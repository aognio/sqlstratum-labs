from __future__ import annotations

import os
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

from faker import Faker
from sqlstratum import INSERT, UPDATE
from sqlstratum.runner import Runner

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from clinicdesk import queries  # noqa: E402


DB_PATH = BASE_DIR / "var" / "clinicdesk.sqlite3"


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS patients(
  id INTEGER PRIMARY KEY,
  full_name TEXT NOT NULL,
  phone TEXT,
  email TEXT,
  dob TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS staff_users(
  id INTEGER PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  role TEXT NOT NULL,
  doctor_id INTEGER,
  pin TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS doctors(
  id INTEGER PRIMARY KEY,
  full_name TEXT NOT NULL,
  specialty TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS services(
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  duration_min INTEGER NOT NULL,
  price_cents INTEGER NOT NULL,
  active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS appointments(
  id INTEGER PRIMARY KEY,
  patient_id INTEGER NOT NULL,
  doctor_id INTEGER NOT NULL,
  service_id INTEGER NOT NULL,
  starts_at TEXT NOT NULL,
  status TEXT NOT NULL,
  notes TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS invoices(
  id INTEGER PRIMARY KEY,
  appointment_id INTEGER UNIQUE NOT NULL,
  patient_id INTEGER NOT NULL,
  total_cents INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS invoice_items(
  id INTEGER PRIMARY KEY,
  invoice_id INTEGER NOT NULL,
  description TEXT NOT NULL,
  qty INTEGER NOT NULL,
  unit_price_cents INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_appointments_patient ON appointments(patient_id, starts_at);
CREATE INDEX IF NOT EXISTS idx_appointments_doctor ON appointments(doctor_id, starts_at);
CREATE INDEX IF NOT EXISTS idx_appointments_status ON appointments(status);
CREATE INDEX IF NOT EXISTS idx_patients_name ON patients(full_name);
CREATE INDEX IF NOT EXISTS idx_invoices_patient ON invoices(patient_id);
"""


def exec_schema(runner: Runner) -> None:
    for stmt in SCHEMA_SQL.strip().split(";"):
        sql = stmt.strip()
        if not sql:
            continue
        runner.exec_ddl(sql)


def main() -> None:
    seed = os.environ.get("SEED")
    if seed is not None:
        random.seed(int(seed))
    faker = Faker()
    if seed is not None:
        faker.seed_instance(int(seed))

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    runner = Runner.connect(str(DB_PATH))
    exec_schema(runner)

    now = datetime.utcnow()

    # Doctors
    specialties = [
        "Family Medicine",
        "Pediatrics",
        "Dermatology",
        "Cardiology",
        "Orthopedics",
        "Neurology",
        "ENT",
        "Gastroenterology",
        "Oncology",
        "Psychiatry",
    ]
    doctor_ids = []
    for i in range(25):
        doc_name = faker.name()
        specialty = random.choice(specialties)
        result = runner.execute(
            INSERT(queries.doctors).VALUES(
                full_name=doc_name,
                specialty=specialty,
                active=1,
            )
        )
        doctor_ids.append(int(result.lastrowid))

    # Services
    service_ids = []
    for _ in range(30):
        service_name = f"{random.choice(['Consult', 'Follow-up', 'Exam', 'Screening', 'Therapy'])} {faker.word().title()}"
        duration = random.choice([20, 30, 40, 45, 60])
        price_cents = random.choice([7500, 8500, 12000, 15000, 18000, 22000])
        result = runner.execute(
            INSERT(queries.services).VALUES(
                name=service_name,
                duration_min=duration,
                price_cents=price_cents,
                active=1,
            )
        )
        service_ids.append(int(result.lastrowid))

    # Patients
    patient_ids = []
    for _ in range(800):
        full_name = faker.name()
        phone = faker.phone_number()
        email = faker.email()
        dob = faker.date_of_birth(minimum_age=18, maximum_age=90).isoformat()
        created_at = (now - timedelta(days=random.randint(0, 700))).isoformat()
        result = runner.execute(
            INSERT(queries.patients).VALUES(
                full_name=full_name,
                phone=phone,
                email=email,
                dob=dob,
                created_at=created_at,
            )
        )
        patient_ids.append(int(result.lastrowid))

    # Staff users
    for idx in range(6):
        runner.execute(
            INSERT(queries.staff_users).VALUES(
                username=f"staff{idx + 1}",
                role="staff",
                doctor_id=None,
                pin="1234",
            )
        )

    # Doctor users
    for idx, doctor_id in enumerate(doctor_ids):
        runner.execute(
            INSERT(queries.staff_users).VALUES(
                username=f"doctor{idx + 1}",
                role="doctor",
                doctor_id=doctor_id,
                pin="1234",
            )
        )

    # Appointments
    appointment_ids = []
    statuses = ["requested", "confirmed", "cancelled", "done"]
    status_weights = [0.2, 0.5, 0.1, 0.2]
    for _ in range(6000):
        patient_id = random.choice(patient_ids)
        doctor_id = random.choice(doctor_ids)
        service_id = random.choice(service_ids)
        day_offset = random.randint(-120, 120)
        start_time = (now + timedelta(days=day_offset, hours=random.randint(8, 17))).replace(minute=0, second=0, microsecond=0)
        status = random.choices(statuses, weights=status_weights, k=1)[0]
        notes = faker.sentence(nb_words=6) if random.random() < 0.15 else None
        created_at = (start_time - timedelta(days=random.randint(1, 40))).isoformat()
        updated_at = (start_time - timedelta(days=random.randint(0, 5))).isoformat()
        result = runner.execute(
            INSERT(queries.appointments).VALUES(
                patient_id=patient_id,
                doctor_id=doctor_id,
                service_id=service_id,
                starts_at=start_time.isoformat(),
                status=status,
                notes=notes,
                created_at=created_at,
                updated_at=updated_at,
            )
        )
        appointment_ids.append(int(result.lastrowid))

    # Invoices + items
    invoice_appointments = random.sample(appointment_ids, 3500)
    for appointment_id in invoice_appointments:
        appointment = queries.get_appointment_detail(runner, appointment_id)
        if appointment is None:
            continue
        result = runner.execute(
            INSERT(queries.invoices).VALUES(
                appointment_id=appointment_id,
                patient_id=appointment["patient_id"],
                total_cents=0,
                status=random.choice(["draft", "issued", "paid"]),
                created_at=(now - timedelta(days=random.randint(0, 60))).isoformat(),
            )
        )
        invoice_id = int(result.lastrowid)

        item_count = random.randint(1, 4)
        total = 0
        for _ in range(item_count):
            qty = random.randint(1, 3)
            unit_price = random.choice([2500, 5000, 7500, 12000])
            total += qty * unit_price
            runner.execute(
                INSERT(queries.invoice_items).VALUES(
                    invoice_id=invoice_id,
                    description=faker.word().title(),
                    qty=qty,
                    unit_price_cents=unit_price,
                )
            )
        runner.execute(
            UPDATE(queries.invoices).SET(total_cents=total).WHERE(queries.invoices.c.id == invoice_id)
        )

    # Summary
    counts = {
        "patients": len(patient_ids),
        "doctors": len(doctor_ids),
        "services": len(service_ids),
        "staff_users": 6 + len(doctor_ids),
        "appointments": len(appointment_ids),
        "invoices": len(invoice_appointments),
    }
    for key, value in counts.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
