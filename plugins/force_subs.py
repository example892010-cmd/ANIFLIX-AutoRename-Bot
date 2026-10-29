"""Persistent, per-channel force-subscription settings and membership verification."""

import logging
from typing import Any

from pyrogram.errors import UserNotParticipant
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import Config
from helper.database import codeflixbots

logger = logging.getLogger(__name__)
_SETTINGS_ID = "global"
_MAX_CHANNELS = 7


def _default_channel(value: Any) -> dict[str, Any]:
    raw = str(value).strip()
    if not raw:
        return {}
    if raw.lstrip("-").isdigit():
        return {"chat_id": int(raw), "join_url": "", "mode": "normal", "title": raw}
    username = raw.lstrip("@").strip()
    return {"chat_id": "@" + username, "join_url": f"https://t.me/{username}", "mode": "normal", "title": username}


async def get_fsub_settings() -> dict[str, Any]:
    """Read DB settings; migrate the legacy environment list when no DB document exists."""
    collection = codeflixbots.codeflixbots["fsub_settings"]
    saved = await collection.find_one({"_id": _SETTINGS_ID})
    if saved:
        channels = saved.get("channels") or []
        return {"enabled": bool(saved.get("enabled", bool(channels))), "channels": channels[:_MAX_CHANNELS]}
    legacy = [_default_channel(value) for value in (Config.FORCE_SUB_CHANNELS or [])]
    legacy = [item for item in legacy if item][:_MAX_CHANNELS]
    return {"enabled": bool(legacy), "channels": legacy}


async def save_fsub_settings(settings: dict[str, Any]) -> None:
    channels = list(settings.get("channels") or [])[:_MAX_CHANNELS]
    await codeflixbots.codeflixbots["fsub_settings"].update_one(
        {"_id": _SETTINGS_ID},
        {"$set": {"enabled": bool(settings.get("enabled", bool(channels))), "channels": channels}},
        upsert=True,
    )


def _member_status(member) -> str:
    status = getattr(member, "status", "")
    return str(getattr(status, "value", status)).casefold().split(".")[-1]


def _member_is_missing(member) -> bool:
    status = _member_status(member)
    if status in {"left", "kicked", "banned"}:
        return True
    if status == "restricted" and not bool(getattr(member, "is_member", False)):
        return True
    return False


async def check_fsub_membership(client, user_id: int) -> tuple[list[dict[str, Any]], list[str]]:
    """Return (channels still to join, verification errors). Errors fail closed for file delivery."""
    settings = await get_fsub_settings()
    if not settings["enabled"] or not settings["channels"]:
        return [], []
    missing: list[dict[str, Any]] = []
    errors: list[str] = []
    for index, channel in enumerate(settings["channels"], start=1):
        target = channel.get("chat_id") or channel.get("username")
        if target is None or str(target).strip() == "":
            errors.append(f"Channel {index} has no chat ID configured.")
            continue
        try:
            member = await client.get_chat_member(target, int(user_id))
            status = _member_status(member)
            if _member_is_missing(member):
                missing.append(channel)
            elif status not in {"member", "administrator", "creator", "owner", "restricted"}:
                # Never silently allow access when Telegram returns an unexpected
                # membership status; the file-delivery handler fails closed on errors.
                errors.append(f"Channel {channel.get('title') or target}: Unknown membership status")
        except UserNotParticipant:
            missing.append(channel)
        except Exception as exc:
            logger.exception("Force-subscription check failed for channel %s", target)
            errors.append(f"Channel {channel.get('title') or target}: {type(exc).__name__}")
    return missing, errors


def subscription_keyboard(channels: list[dict[str, Any]], token: str) -> InlineKeyboardMarkup:
    rows = []
    for index, channel in enumerate(channels, start=1):
        url = (channel.get("join_url") or "").strip()
        if not url:
            username = str(channel.get("username") or channel.get("chat_id") or "").strip()
            if username.startswith("@"):
                url = "https://t.me/" + username[1:]
            elif not username.lstrip("-").isdigit() and username:
                url = "https://t.me/" + username
        # Normalize accepted Telegram invite hosts so every saved valid link
        # actually appears as a Join button.
        if url.startswith(("https://t.me/", "http://t.me/", "https://www.t.me/", "https://telegram.me/", "https://www.telegram.me/")):
            if url.startswith(("https://www.t.me/", "https://telegram.me/", "https://www.telegram.me/", "http://t.me/")):
                url = "https://t.me/" + url.split("/", 3)[-1]
            label = str(channel.get("title") or f"Channel {index}")[:50]
            rows.append([InlineKeyboardButton(f"📢 Join {label}", url=url)])
    rows.append([InlineKeyboardButton("♻️ Try Again", callback_data=f"check_file_sub:{token}")])
    return InlineKeyboardMarkup(rows)


def is_admin(user_id: int) -> bool:
    from helper.auth import is_admin_user
    return is_admin_user(user_id)
