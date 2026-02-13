from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "bookinglab.db"


class Config:
    SECRET_KEY = os.environ.get("BOOKINGLAB_SECRET", "dev-secret")
    DB_PATH = os.environ.get("BOOKINGLAB_DB", str(DB_PATH))
    ITEMS_PER_PAGE = int(os.environ.get("BOOKINGLAB_PAGE_SIZE", "20"))
    MAX_SEATS_PER_BOOKING = int(os.environ.get("BOOKINGLAB_MAX_SEATS", "10"))
