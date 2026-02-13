from __future__ import annotations

from functools import wraps
from flask import session, redirect, url_for, request, g


def login_user(user_id: int, role: str, display_name: str) -> None:
    session.clear()
    session["user_id"] = user_id
    session["role"] = role
    session["display_name"] = display_name


def logout_user() -> None:
    session.clear()


def get_session_user() -> dict | None:
    user_id = session.get("user_id")
    role = session.get("role")
    display_name = session.get("display_name")
    if user_id is None or role is None:
        return None
    return {"id": user_id, "role": role, "display_name": display_name}


def require_role(*roles: str):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = get_session_user()
            if user is None:
                return redirect(url_for("login", next=request.path))
            if roles and user["role"] not in roles:
                return redirect(url_for("login"))
            g.current_user = user
            return view(*args, **kwargs)

        return wrapped

    return decorator
