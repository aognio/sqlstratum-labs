from __future__ import annotations

import sqlite3
from pathlib import Path
from sqlstratum.runner import Runner

from bookinglab.config import Config
from bookinglab.schema import SCHEMA_SQL


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_runner() -> Runner:
    db_path = Path(Config.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = _connect(str(db_path))
    return Runner(conn)


def init_db() -> None:
    db_path = Path(Config.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = _connect(str(db_path))
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()
