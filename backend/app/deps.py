"""Shared FastAPI dependencies: authentication, role checks, and audit logging.

Centralised here so every router (heroes, hypotheses, portfolio, knowledge base)
reuses the same auth + permission + audit plumbing. ``main.py`` re-exports these
for its own endpoints.
"""

from __future__ import annotations

from typing import Any, Callable

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from mirrorquant_demo.database import get_session
from mirrorquant_demo.models import AuditLog, User
from mirrorquant_demo.permissions import role_at_least


def get_current_user(
    request: Request,
    session: Session = Depends(get_session),
) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = session.get(User, user_id)
    if user is None:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Not authenticated")

    return user


def get_current_verified_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_verified:
        raise HTTPException(status_code=403, detail="Verify your email before using MirrorQuant.")
    return current_user


def require_role(required: str) -> Callable[..., User]:
    """Dependency factory enforcing a minimum role (viewer < analyst < admin)."""

    def _dependency(current_user: User = Depends(get_current_verified_user)) -> User:
        if not role_at_least(getattr(current_user, "role", None), required):
            raise HTTPException(
                status_code=403,
                detail=f"This action requires the '{required}' role.",
            )
        return current_user

    return _dependency


def record_audit(
    session: Session,
    *,
    user_id: int | None,
    action: str,
    target_type: str | None = None,
    target_id: str | int | None = None,
    detail: dict[str, Any] | None = None,
    request: Request | None = None,
    commit: bool = True,
) -> None:
    """Append an entry to the audit trail. Best-effort: never breaks the request."""
    try:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=None if target_id is None else str(target_id),
            detail_json=detail,
            ip_address=(request.client.host if request and request.client else None),
        )
        session.add(entry)
        if commit:
            session.commit()
    except Exception:  # pragma: no cover - audit must not break the main flow
        session.rollback()
