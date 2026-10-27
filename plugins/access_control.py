"""Server-side member restrictions: normal members may only open saved file links."""

import logging
import re

from pyrogram import Client, filters
from pyrogram import StopPropagation

from helper.auth import is_admin_user

logger = logging.getLogger(__name__)
_FILE_START_RE = re.compile(r"^/start(?:@\w+)?\s+file_[A-Za-z0-9_-]{1,60}\s*$", re.IGNORECASE)
_ALLOWED_CALLBACK_RE = re.compile(r"^check_file_sub:[A-Za-z0-9_-]{1,60}$")


@Client.on_message(group=-10)
async def members_file_access_only(client, message):
    user = getattr(message, "from_user", None)
    if user is None or is_admin_user(user):
        return
    text = (getattr(message, "text", None) or getattr(message, "caption", None) or "").strip()
    chat_type = str(getattr(getattr(getattr(message, "chat", None), "type", None), "value", getattr(getattr(message, "chat", None), "type", ""))).casefold().split(".")[-1]
    if chat_type == "private" and text and _FILE_START_RE.fullmatch(text):
        return
    if chat_type == "private":
        try:
            await message.reply_text(
                "🔒 This bot is for file access only.\n\n"
                "Open a 480p, 720p, or 1080p button from an ANIFLIX post to get its file. "
                "Rename commands and other features are admin-only."
            )
        except Exception:
            logger.exception("Could not send member access restriction")
    raise StopPropagation


@Client.on_callback_query(group=-10)
async def members_callback_access_only(client, query):
    if is_admin_user(getattr(query, "from_user", None)):
        return
    data = (getattr(query, "data", None) or "").strip()
    if _ALLOWED_CALLBACK_RE.fullmatch(data):
        return
    try:
        await query.answer("Use a file-quality link from an ANIFLIX post.", show_alert=True)
    except Exception:
        logger.debug("Could not answer restricted callback", exc_info=True)
    raise StopPropagation
