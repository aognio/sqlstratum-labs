from __future__ import annotations

from typing import Optional
from starlette.requests import Request


def login_user(request: Request, user_id: int, role: str, display_name: str) -> None:
    request.session.clear()
    request.session["user_id"] = user_id
    request.session["role"] = role
    request.session["display_name"] = display_name


def logout_user(request: Request) -> None:
    request.session.clear()


def get_session_user(request: Request) -> Optional[dict]:
    user_id = request.session.get("user_id")
    role = request.session.get("role")
    display_name = request.session.get("display_name")
    if user_id is None or role is None:
        return None
    return {"id": user_id, "role": role, "display_name": display_name}


def require_role(request: Request, *roles: str) -> Optional[dict]:
    user = get_session_user(request)
    if user is None:
        return None
    if roles and user["role"] not in roles:
        return None
    return user
