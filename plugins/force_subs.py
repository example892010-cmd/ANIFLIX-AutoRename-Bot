"""Optional force-subscribe gate. Disabled when no channels are configured."""

import logging

from pyrogram import Client, filters
from pyrogram.errors import UserNotParticipant
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

from config import Config

logger = logging.getLogger(__name__)
FORCE_SUB_CHANNELS = Config.FORCE_SUB_CHANNELS
IMAGE_URL = "https://graph.org/file/a27d85469761da836337c.jpg"


def _is_not_member(member) -> bool:
    status = getattr(member, "status", "")
    status = str(getattr(status, "value", status)).lower().split(".")[-1]
    return status in {"left", "kicked"}


async def _get_missing_channels(client, user_id: int) -> list[str]:
    missing = []
    for channel in FORCE_SUB_CHANNELS:
        try:
            member = await client.get_chat_member(channel, user_id)
            if _is_not_member(member):
                missing.append(channel)
        except UserNotParticipant:
            missing.append(channel)
        except Exception:
            # A misconfigured or inaccessible channel should not crash the bot or
            # accidentally block every user. Log it for the owner to correct.
            logger.exception("Could not verify force-sub channel %s", channel)
    return missing


async def not_subscribed(_, client, message):
    if not FORCE_SUB_CHANNELS or not getattr(message, "from_user", None):
        return False
    missing = await _get_missing_channels(client, message.from_user.id)
    return bool(missing)


def _join_url(channel: str) -> str | None:
    channel = str(channel).strip().lstrip("@")
    if channel.startswith("-") or channel.lstrip("0123456789") == "":
        return None
    return f"https://t.me/{channel}"


def _subscription_buttons(channels: list[str]) -> InlineKeyboardMarkup:
    rows = []
    for channel in channels:
        url = _join_url(channel)
        if url:
            rows.append([InlineKeyboardButton(f"Join {channel}", url=url)])
    rows.append([InlineKeyboardButton("I've joined — check again", callback_data="check_subscription")])
    return InlineKeyboardMarkup(rows)


@Client.on_message(filters.private & filters.create(not_subscribed))
async def forces_sub(client, message):
    missing = await _get_missing_channels(client, message.from_user.id)
    if not missing:
        return

    text = (
        "You need to join the required channel(s) before using this bot. "
        "Join them below, then tap ‘I've joined — check again’."
    )
    await message.reply_photo(
        photo=IMAGE_URL,
        caption=text,
        reply_markup=_subscription_buttons(missing),
    )


@Client.on_callback_query(filters.regex(r"^check_subscription$"))
async def check_subscription(client, callback_query: CallbackQuery):
    try:
        missing = await _get_missing_channels(client, callback_query.from_user.id)
        if not missing:
            await callback_query.answer("Subscription verified!")
            if callback_query.message:
                await callback_query.message.edit_caption(
                    caption="✅ Subscription verified. You can now use the bot. Send /start to continue.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("Open bot menu", callback_data="help")
                    ]]),
                )
            return

        await callback_query.answer("Please join all required channels first.", show_alert=True)
        if callback_query.message:
            await callback_query.message.edit_caption(
                caption="You still need to join the required channel(s) below.",
                reply_markup=_subscription_buttons(missing),
            )
    except Exception:
        logger.exception("Force-subscription verification failed")
        try:
            await callback_query.answer("Couldn't verify membership. Please try again.", show_alert=True)
        except Exception:
            pass
