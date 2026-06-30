"""Role definitions and checks for the Permission & Log System.

Three coarse roles ordered by privilege. Kept as plain helpers (no framework
coupling) so both the API layer and services can use them.
"""

from __future__ import annotations

VIEWER = "viewer"
ANALYST = "analyst"
ADMIN = "admin"

ROLES = (VIEWER, ANALYST, ADMIN)
DEFAULT_ROLE = ANALYST

_RANK = {VIEWER: 0, ANALYST: 1, ADMIN: 2}


def normalize_role(role: str | None) -> str:
    role = (role or "").strip().lower()
    return role if role in _RANK else DEFAULT_ROLE


def role_at_least(user_role: str | None, required: str) -> bool:
    """True if ``user_role`` is at or above the ``required`` role."""
    return _RANK[normalize_role(user_role)] >= _RANK[normalize_role(required)]
