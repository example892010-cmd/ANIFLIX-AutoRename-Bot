"""Small, dependency-free helpers for resolving ongoing-channel destinations."""
from typing import Any

MAX_ONGOING_CHANNELS = 6


def assigned_ongoing_targets(route: dict) -> list[Any]:
    """Return anime-specific destinations, preserving order and removing duplicates."""
    values = route.get("ongoing_channels") or []
    if not values and route.get("ongoing_channel"):
        values = [route.get("ongoing_channel")]
    result, seen = [], set()
    for value in values:
        if value is None or not str(value).strip():
            continue
        identity = str(value).casefold()
        if identity not in seen:
            seen.add(identity)
            result.append(value)
    return result[:MAX_ONGOING_CHANNELS]


async def resolve_ongoing_targets(route: dict, database) -> list[Any]:
    """Use per-anime targets first, falling back to active globally saved channels."""
    assigned = assigned_ongoing_targets(route)
    if assigned:
        return assigned
    doc = await database["ongoing_channel_settings"].find_one({"_id": "global"}) or {}
    result, seen = [], set()
    for item in doc.get("channels") or []:
        if item.get("active", True) is False:
            continue
        value = item.get("chat_id", item.get("target"))
        if value is None or not str(value).strip():
            continue
        if isinstance(value, str) and value.lstrip("-").isdigit():
            value = int(value)
        identity = str(value).casefold()
        if identity not in seen:
            seen.add(identity)
            result.append(value)
    return result[:MAX_ONGOING_CHANNELS]
