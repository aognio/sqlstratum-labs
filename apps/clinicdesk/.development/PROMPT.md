You are Codex. Build a realistic “exploration + stress test” web app that uses sqlstratum + SQLite in a non-trivial way. The purpose of this project is to validate sqlstratum under real application load patterns (joins, aggregates, pagination, search, transactions), not to build a production system.

You are working inside an existing repo that already contains the sqlstratum package (local source). Use the repo root as the standalone Flask app that imports and uses the local sqlstratum code from the repo (either via editable install instructions or by adjusting PYTHONPATH). The app must use SQLite as the only database.

========================================
Project concept
========================================
Name: ClinicDesk (sqlstratum stress-test app)

Two surfaces:
1) Patient / customer surface (public-ish):
   - patient can “log in” (simple passwordless or demo PIN is fine)
   - patient can see their profile, upcoming appointments, past appointments
   - patient can request/book an appointment (choosing service + doctor + time slot)
   - patient can see invoice summary for their appointments (read-only)

2) Staff / doctors surface (internal):
   - staff login (simple demo auth, role-based: staff vs doctor)
   - staff dashboard with KPIs (counts/aggregates)
   - staff can search patients, view patient detail, see appointment history
   - staff can create/confirm/reschedule/cancel appointments (transactional)
   - doctor view: “my schedule” page filtered to that doctor, update appointment status and notes
   - invoices: staff can generate invoice for an appointment and add line items

UI stack:
- Flask + Jinja2 templates
- HTMX for partial updates (search results, appointment list refresh, inline edits)
- AlpineJS for small interactions (modals, toggles)
- Tailwind CSS (use CDN to avoid build tooling)

========================================
Why this is a sqlstratum stress test
========================================
The app must intentionally exercise:
- JOIN-heavy listings (appointments joined with patients, doctors, services)
- pagination + sorting + filtering combined
- search-as-you-type via HTMX (LIKE/contains)
- aggregates (COUNT/SUM) for dashboard KPIs
- transactions: booking/rescheduling must be atomic (insert/update + invoice generation)
- hydration: default dict hydration everywhere; ensure JSON serializable responses for HTMX endpoints where appropriate

All database reads/writes must use sqlstratum (SELECT/INSERT/UPDATE/DELETE). Raw SQL is allowed ONLY for initial schema creation and optional indexes in migrations-less setup.

========================================
Data model (SQLite tables)
========================================
Implement schema with raw SQL in a setup step (NOT in sqlstratum core). Include:

patients(
  id INTEGER PRIMARY KEY,
  full_name TEXT NOT NULL,
  phone TEXT,
  email TEXT,
  dob TEXT,
  created_at TEXT NOT NULL
)

staff_users(
  id INTEGER PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  role TEXT NOT NULL,               -- "staff" or "doctor"
  doctor_id INTEGER,                -- nullable for staff
  pin TEXT NOT NULL                 -- demo auth
)

doctors(
  id INTEGER PRIMARY KEY,
  full_name TEXT NOT NULL,
  specialty TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1
)

services(
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  duration_min INTEGER NOT NULL,
  price_cents INTEGER NOT NULL,
  active INTEGER NOT NULL DEFAULT 1
)

appointments(
  id INTEGER PRIMARY KEY,
  patient_id INTEGER NOT NULL,
  doctor_id INTEGER NOT NULL,
  service_id INTEGER NOT NULL,
  starts_at TEXT NOT NULL,
  status TEXT NOT NULL,             -- "requested", "confirmed", "cancelled", "done"
  notes TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
)

invoices(
  id INTEGER PRIMARY KEY,
  appointment_id INTEGER UNIQUE NOT NULL,
  patient_id INTEGER NOT NULL,
  total_cents INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL,             -- "draft", "issued", "paid"
  created_at TEXT NOT NULL
)

invoice_items(
  id INTEGER PRIMARY KEY,
  invoice_id INTEGER NOT NULL,
  description TEXT NOT NULL,
  qty INTEGER NOT NULL,
  unit_price_cents INTEGER NOT NULL
)

Indexes (optional but recommended):
- appointments(patient_id, starts_at)
- appointments(doctor_id, starts_at)
- appointments(status)
- patients(full_name)
- invoices(patient_id)

========================================
Synthetic test data generation
========================================
Generate hundreds/thousands of records to stress queries. Use a “proper Python library” for synthetic data:
- Use Faker (external dependency) for names/emails/phones and realistic text.

Target dataset (minimum):
- 800 patients
- 25 doctors
- 30 services
- 6 staff users (role=staff)
- 25 doctor users (role=doctor, linked doctor_id)
- 6,000 appointments distributed over +/- 120 days
- 3,500 invoices + invoice_items (1–4 items each)

Create a script:
  scripts/seed.py

that:
- creates database file (var/clinicdesk.sqlite3)
- runs schema SQL
- inserts all synthetic data using sqlstratum for DML (INSERT/UPDATE/DELETE)
- prints summary counts
- is deterministic if SEED env var is set

Dependency management:
- create requirements.txt including: Flask, Faker
- do NOT add heavyweight ORMs
- you may add python-dotenv optionally, but keep dependencies minimal

========================================
App structure
========================================
Create:
README.md
requirements.txt
run.sh (optional convenience)
clinicdesk/
  __init__.py
  app.py
  config.py
  auth.py
  db.py            -- Runner setup, connection path, helpers
  queries.py       -- all sqlstratum queries centralized (very important)
  views/
    patient.py
    staff.py
    doctor.py
  templates/
    base.html
    login.html
    patient/
    staff/
    doctor/
  static/ (optional, but prefer CDN for Tailwind/Alpine/HTMX)
scripts/
  seed.py
  init_db.py (optional: schema-only)
var/
  (sqlite db lives here; gitignored)

Use Flask Blueprints:
- /patient/* routes
- /staff/* routes
- /doctor/* routes
- /login, /logout

Auth:
- Keep it simple:
  - login form where user enters username + PIN
  - session cookie stores user_id and role
  - role-based decorators to protect routes

========================================
Core features (must implement)
========================================
Patient surface:
- Patient home: next 5 upcoming appointments + last 5 past appointments
- Patient appointments list: filter by status + date range, paginated
- Patient request appointment:
  - choose service and preferred doctor OR “any doctor”
  - choose a day; backend shows available slots (simple heuristic, not perfect scheduling)
  - create appointment with status="requested"

Staff surface:
- Dashboard: KPIs (must be sqlstratum aggregates)
  - appointments today
  - requested appointments pending
  - revenue last 7 days (sum invoices.total_cents)
  - active doctors count
  - most booked service (group by service_id)
- Patients list with HTMX live search (search by name/email/phone)
- Patient detail with appointment history
- Appointments board:
  - filter by status, doctor, date range
  - actions via HTMX: confirm, cancel, reschedule
  - reschedule should be transactional (update starts_at + updated_at)
- Invoice management:
  - generate invoice for appointment (if absent) with default line item from service price
  - add/remove invoice items via HTMX
  - recompute total_cents in a transaction

Doctor surface:
- My schedule: appointments for this doctor (today default), paginated
- Update appointment status and notes (HTMX inline edit)

========================================
sqlstratum usage rules
========================================
- ALL DML and SELECT must be expressed via sqlstratum queries in clinicdesk/queries.py
- Use joins and explicit aliases to avoid key collisions in dict hydration
- Use ORDER_BY + LIMIT/OFFSET for pagination
- Use WHERE with implicit AND, OR(...) for disjunctions
- Use COUNT/SUM aggregates for dashboard KPIs
- Use Runner.transaction() for multi-step workflows (invoice creation + items + total update)

========================================
README framing (very important)
========================================
README.md must clearly say:
- This is a stress test and exploration project for sqlstratum + SQLite
- Not production-ready; auth is demo; scheduling is simplified
- The point is to exercise joins, aggregates, pagination, filters, transactions, hydration
- Provide quickstart commands:
  - python -m venv .venv && source .venv/bin/activate
  - pip install -r requirements.txt
  - python scripts/seed.py
  - flask --app clinicdesk.app run
- Provide test instructions if you add tests (optional but appreciated)

Also add a short section: “sqlstratum queries worth reading” pointing to clinicdesk/queries.py.

========================================
Quality bar
========================================
- Keep HTML templates clean and readable.
- Use HTMX patterns: hx-get, hx-post, hx-target, hx-swap.
- Use Alpine only for small UI state, not for data.
- Ensure all endpoints render both full pages and partials where relevant (HTMX).
- Keep queries centralized and named; avoid query logic scattered in route handlers.
- Ensure seed data is large enough to make pagination/search meaningful.

========================================
Package location
========================================

The sources to the sqlstratum packages are located at:

/Users/gnrfan/code/experiments/web-tooling/sqlstratum

Install it to the virtual environment you create.

=======================================
Feedback and suggestions
=======================================

Write all sort of criticisms and feeback in free format but respecting the .md format
inside a .feeback folder. Use the .scrapbook folder to keep free form .md notes for 
yourself so you can remember things and generate a very coherent feedback and suggestion
article using the explainer prose set of writing constrains.

========================================
Start now
========================================
Implement the full project in the repo root. Ensure it runs end-to-end after seeding. Use local sqlstratum package from repo. Provide a working README with clear framing and commands.
