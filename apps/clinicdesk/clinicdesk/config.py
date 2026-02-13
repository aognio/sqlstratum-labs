from __future__ import annotations

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
VAR_DIR = BASE_DIR / "var"
DEFAULT_DB_PATH = VAR_DIR / "clinicdesk.sqlite3"


class Config:
    SECRET_KEY = os.environ.get("CLINICDESK_SECRET", "dev-secret")
    DB_PATH = os.environ.get("CLINICDESK_DB", str(DEFAULT_DB_PATH))
    ITEMS_PER_PAGE = int(os.environ.get("CLINICDESK_PAGE_SIZE", "20"))
