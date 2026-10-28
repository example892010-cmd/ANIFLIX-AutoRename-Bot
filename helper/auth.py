"""Shared, defensive admin-ID parsing for message and callback handlers."""

import os

from config import Config


def admin_ids() -> set[int]:
    allowed = {int(value) for value in (getattr(Config, "ADMIN", []) or [])}
    for name in ("OWNER_ID", "OWNERID", "ADMIN_ID", "ADMIN"):
        raw = os.environ.get(name, "").strip()
        for item in raw.replace(",", " ").split() if raw else []:
            try:
                allowed.add(int(item))
            except ValueError:
                continue
    return allowed


def is_admin_user(user_or_id) -> bool:
    value = getattr(user_or_id, "id", user_or_id)
    try:
        return int(value) in admin_ids()
    except (TypeError, ValueError):
        return False
