# ClinicDesk (sqlstratum stress-test app)

ClinicDesk is a **stress test and exploration project** for `sqlstratum` + SQLite. It is **not production-ready**: auth is demo-only, scheduling is simplified, and data modeling is intentionally minimal. The goal is to exercise joins, aggregates, pagination, filters, transactions, and hydration behavior under realistic query patterns.

## Quickstart

```bash
cd apps/clinicdesk
python -m venv .env
source .env/bin/activate
pip install -r requirements.txt
python scripts/seed.py
./run.sh
```

Then open `http://127.0.0.1:5001`.

Demo logins:
- Staff: `staff1` / `1234`
- Doctor: `doctor1` / `1234`
- Patient: use any seeded patient `email` + `DOB`

## What This App Exercises

- JOIN-heavy listings (appointments ↔ patients ↔ doctors ↔ services)
- Aggregates (dashboard KPIs, revenue sums, most-booked service)
- Pagination + filtering + sorting
- Search-as-you-type via HTMX
- Transactions for rescheduling and invoice updates
- Dict hydration and explicit aliasing to avoid collisions

## sqlstratum Queries Worth Reading

See `clinicdesk/queries.py` for all SELECT/DML statements and query composition patterns.

## Notes

- All reads/writes go through sqlstratum. Raw SQL is only used for schema creation.
- SQLite is the only database.
- The dataset seeded by `scripts/seed.py` is intentionally large to make pagination and search meaningful.
