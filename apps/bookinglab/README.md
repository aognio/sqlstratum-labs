# BookingLab (Event Booking stretching the limits app)

BookingLab is a FastAPI + SQLite lab app for stretching the limits of SQLStratum query patterns and Pydantic hydration. It is **not production software**.

## Setup

```bash
cd apps/bookinglab
python -m venv .env
source .env/bin/activate
pip install -U pip
pip install -r requirements.txt
```

## Initialize + seed database

```bash
python scripts/seed.py --reset
```

The SQLite DB is stored at `data/bookinglab.db`.

## Run the server

```bash
./run.sh
```

Open `http://127.0.0.1:5002`.

Demo staff login:
- `admin1` / `1234`
- `staff1` / `1234`

## SQL debug logging

SQLStratum logs compiled SQL + params when both are enabled:

```bash
SQLSTRATUM_DEBUG=1 ./run.sh
```

Make sure logging is configured in `bookinglab/app.py` (already enabled when `SQLSTRATUM_DEBUG` is truthy).

## What this app exercises

- Pydantic v2 hydration (nested models, enums, validators)
- Joins and aggregates (events ↔ bookings ↔ attendees)
- Pagination and search
- Transactional booking creation with capacity checks
