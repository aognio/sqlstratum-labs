from __future__ import annotations

import sqlite3
from pathlib import Path
from flask import g, current_app
from sqlstratum.runner import Runner


def get_runner() -> Runner:
    if "runner" not in g:
        db_path = Path(current_app.config["DB_PATH"])
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        g.runner = Runner(conn)
    return g.runner


def close_db(e=None) -> None:  # noqa: ARG001
    runner = g.pop("runner", None)
    if runner is not None:
        runner.connection.close()


def init_app(app) -> None:
    app.teardown_appcontext(close_db)
