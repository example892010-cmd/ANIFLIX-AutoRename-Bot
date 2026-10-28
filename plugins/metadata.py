"""Commands for toggling and configuring optional media metadata."""

import logging
from html import escape

from pyrogram import Client, enums, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

from config import Txt
from helper.database import codeflixbots as db
from helper.file_names import metadata_enabled

logger = logging.getLogger(__name__)


def _metadata_keyboard(current: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"On{' ✅' if current == 'On' else ''}", callback_data="on_metadata"),
            InlineKeyboardButton(f"Off{' ✅' if current == 'Off' else ''}", callback_data="off_metadata"),
        ],
        [InlineKeyboardButton("How to Set Metadata", callback_data="metainfo")],
    ])


async def _metadata_text(user_id: int) -> str:
    enabled = metadata_enabled(await db.get_metadata(user_id))
    current = "On" if enabled else "Off"
    title = await db.get_title(user_id)
    author = await db.get_author(user_id)
    artist = await db.get_artist(user_id)
    video = await db.get_video(user_id)
    audio = await db.get_audio(user_id)
    subtitle = await db.get_subtitle(user_id)
    def safe(value) -> str:
        return escape(str(value or "Not found"))

    return (
        f"<b>㊋ Your metadata is currently: {current}</b>\n\n"
        f"<b>◈ Title ▹</b> <code>{safe(title)}</code>\n"
        f"<b>◈ Author ▹</b> <code>{safe(author)}</code>\n"
        f"<b>◈ Artist ▹</b> <code>{safe(artist)}</code>\n"
        f"<b>◈ Audio ▹</b> <code>{safe(audio)}</code>\n"
        f"<b>◈ Subtitle ▹</b> <code>{safe(subtitle)}</code>\n"
        f"<b>◈ Video ▹</b> <code>{safe(video)}</code>"
    )


@Client.on_message(filters.private & filters.command("metadata"))
async def metadata(client, message):
    try:
        text = await _metadata_text(message.from_user.id)
        current = "On" if metadata_enabled(await db.get_metadata(message.from_user.id)) else "Off"
        await message.reply_text(
            text=text,
            reply_markup=_metadata_keyboard(current),
            disable_web_page_preview=True,
            parse_mode=enums.ParseMode.HTML,
        )
    except Exception:
        logger.exception("Could not show metadata settings")
        await message.reply_text("❌ Couldn't load metadata settings. Please try again.")


@Client.on_callback_query(filters.regex(r"^(on_metadata|off_metadata|metainfo)$"))
async def metadata_callback(client, query: CallbackQuery):
    user_id = query.from_user.id
    data = query.data
    try:
        if data == "metainfo":
            await query.answer()
            await query.message.edit_text(
                text=Txt.META_TXT,
                disable_web_page_preview=True,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Home", callback_data="home"),
                    InlineKeyboardButton("Close", callback_data="close"),
                ]]),
            )
            return

        await db.set_metadata(user_id, "On" if data == "on_metadata" else "Off")
        await query.answer("Metadata enabled" if data == "on_metadata" else "Metadata disabled")
        current = "On" if data == "on_metadata" else "Off"
        await query.message.edit_text(
            text=await _metadata_text(user_id),
            reply_markup=_metadata_keyboard(current),
            disable_web_page_preview=True,
            parse_mode=enums.ParseMode.HTML,
        )
    except Exception:
        logger.exception("Could not update metadata setting for user %s", user_id)
        try:
            await query.answer("Couldn't update metadata settings", show_alert=True)
        except Exception:
            pass


async def _set_field(message, field_name: str, setter, example: str) -> None:
    if len(message.command) == 1:
        await message.reply_text(f"Please provide a value. Example: /{field_name} {example}")
        return
    value = message.text.split(maxsplit=1)[1].strip()
    if not value:
        await message.reply_text("❌ Value cannot be empty.")
        return
    if len(value) > 500:
        await message.reply_text("❌ Metadata values must be 500 characters or fewer.")
        return
    await setter(message.from_user.id, value)
    await message.reply_text(f"✅ {field_name[3:].capitalize()} saved.")


@Client.on_message(filters.private & filters.command("settitle"))
async def title(client, message):
    await _set_field(message, "settitle", db.set_title, "Encoded by ANIFLIX")


@Client.on_message(filters.private & filters.command("setauthor"))
async def author(client, message):
    await _set_field(message, "setauthor", db.set_author, "ANIFLIX")


@Client.on_message(filters.private & filters.command("setartist"))
async def artist(client, message):
    await _set_field(message, "setartist", db.set_artist, "ANIFLIX")


@Client.on_message(filters.private & filters.command("setaudio"))
async def audio(client, message):
    await _set_field(message, "setaudio", db.set_audio, "Tamil Audio")


@Client.on_message(filters.private & filters.command("setsubtitle"))
async def subtitle(client, message):
    await _set_field(message, "setsubtitle", db.set_subtitle, "Tamil Subtitles")


@Client.on_message(filters.private & filters.command("setvideo"))
async def video(client, message):
    await _set_field(message, "setvideo", db.set_video, "ANIFLIX NETWORK TAMIL")
