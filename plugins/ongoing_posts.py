"""Admin-triggered ongoing posts using saved templates, posters, and invite links."""

import logging
import re
from typing import Any

from pyrogram import Client, enums, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from helper.auth import is_admin_user
from helper.database import codeflixbots
from helper.file_names import normalize_anime_title

logger = logging.getLogger(__name__)
DEFAULT_ONGOING_TEMPLATE = (
    "✦ {title}╭━━━━━━━━━━━━━━━━━━━━━━\n"
    "‣ Season : {season}\n"
    "‣ Episode : {episode_range}\n"
    "‣ Status : {status}\n"
    "‣ Audio : [Tamil Audio]\n"
    "‣ Quality : {qualities}╰━━━━━━━━━━━━━━━━━━━━━━\n"
    "✦ Powered By : @ANIFLIXANIMETAMIL"
)


def _title_key(title: str) -> str:
    return normalize_anime_title((title or "").strip())


class _SafeValues(dict):
    def __missing__(self, key):
        return ""


def _render_template(template: str, values: dict[str, Any], limit: int = 4096) -> str:
    text = (template or DEFAULT_ONGOING_TEMPLATE).strip()
    # The placeholders are authored by the admin. Unknown keys become empty rather than crashing.
    try:
        text = text.format_map(_SafeValues(values))
    except (ValueError, TypeError, KeyError):
        logger.exception("Invalid ongoing post template; falling back to default")
        text = DEFAULT_ONGOING_TEMPLATE.format_map(_SafeValues(values))
    return text[:limit]


def _targets(route: dict) -> list[Any]:
    values = route.get("ongoing_channels") or []
    if not values and route.get("ongoing_channel"):
        values = [route.get("ongoing_channel")]
    result = []
    seen = set()
    for value in values:
        if value is None or str(value).strip() == "":
            continue
        key = str(value).casefold()
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result[:6]


def _invite_keyboard(links: list[dict]) -> InlineKeyboardMarkup | None:
    buttons = []
    for item in links[:100]:
        label = str(item.get("label") or "Open Link").strip()[:64]
        url = str(item.get("url") or "").strip()
        if label and url.startswith(("https://", "http://")):
            buttons.append(InlineKeyboardButton(label, url=url))
    if not buttons:
        return None
    return InlineKeyboardMarkup([buttons[index:index + 2] for index in range(0, len(buttons), 2)])


async def post_ongoing_anime(client: Client, title: str) -> str:
    """Publish the saved ongoing post for one anime to its mapped ongoing channels."""
    key = _title_key(title)
    if not key:
        return "❌ Send an anime title, e.g. /ongoing Naruto Shippuden."
    route = await codeflixbots.codeflixbots["anime_routes"].find_one({"title_key": key})
    if not route:
        route = await codeflixbots.codeflixbots["anime_routes"].find_one({"title": {"$regex": "^" + re.escape(title.strip()) + "$", "$options": "i"}})
    if not route:
        return f"❌ No saved channel/template settings were found for {title}. Add it in Admin Panel → Anime Channels."

    invite_doc = await codeflixbots.codeflixbots["anime_invite_links"].find_one({"_id": route.get("title_key") or key})
    if not invite_doc or not invite_doc.get("links"):
        return f"❌ No invite links are saved for {route.get('title', title)}. Open Admin Panel → Anime Invite Links → Add Links first."
    keyboard = _invite_keyboard(invite_doc.get("links") or [])
    if not keyboard:
        return "❌ No valid URL buttons were found in the saved invite links. Edit the links and try again."

    targets = _targets(route)
    if not targets:
        return f"❌ No ongoing channel is assigned to {route.get('title', title)}. Configure it in Admin Panel → Anime Channels."

    details = route.get("ongoing_details") or {}
    qualities = details.get("qualities") or "480p, 720p, 1080p"
    post_settings = await codeflixbots.codeflixbots["post_template_settings"].find_one({"_id": "global"}) or {}
    # Named Templates hold the poster matched by the normalized anime name. The post
    # text comes from one global Main Ongoing Post Text setting shared by all anime.
    saved_template = await codeflixbots.codeflixbots["anime_templates"].find_one({"_id": key}) or {}
    values = {
        "anime": route.get("title") or title,
        "title": route.get("title") or title,
        "season": details.get("season") or "—",
        "episode_range": details.get("episode_range") or "—",
        "episode": details.get("episode_range") or "—",
        "tag": details.get("tag") or "",
        "status": details.get("status") or "ONGOING",
        "qualities": qualities,
        "audio": "Tamil Audio",
    }
    template = post_settings.get("ongoing_template") or DEFAULT_ONGOING_TEMPLATE
    poster = saved_template.get("poster_file_id") or route.get("poster_file_id")
    # Telegram photo captions are limited to 1024 characters; text posts can be longer.
    caption = _render_template(template, values, limit=1024 if poster else 4096)

    success = []
    failures = []
    for target in targets:
        try:
            chat = await client.get_chat(target)
            try:
                if poster:
                    sent = await client.send_photo(
                        chat_id=chat.id,
                        photo=poster,
                        caption=caption,
                        reply_markup=keyboard,
                        parse_mode=enums.ParseMode.HTML,
                    )
                else:
                    sent = await client.send_message(
                        chat_id=chat.id,
                        text=caption,
                        reply_markup=keyboard,
                        parse_mode=enums.ParseMode.HTML,
                        disable_web_page_preview=True,
                    )
            except Exception as exc:
                error_text = str(exc).casefold()
                # Fall back to plain text only when template HTML is malformed. Other failures
                # (permissions, missing poster, inaccessible channel) are reported normally.
                if not ("parse entities" in error_text or "can't parse" in error_text or "unsupported start tag" in error_text):
                    raise
                logger.warning("Ongoing template HTML could not be parsed; retrying as plain text")
                if poster:
                    sent = await client.send_photo(
                        chat_id=chat.id,
                        photo=poster,
                        caption=caption,
                        reply_markup=keyboard,
                        parse_mode=enums.ParseMode.DISABLED,
                    )
                else:
                    sent = await client.send_message(
                        chat_id=chat.id,
                        text=caption,
                        reply_markup=keyboard,
                        parse_mode=enums.ParseMode.DISABLED,
                        disable_web_page_preview=True,
                    )
            success.append(f"{getattr(chat, 'title', None) or target} (message {sent.id})")
        except Exception as exc:
            logger.exception("Ongoing post failed for %s", target)
            failures.append(f"{target}: {type(exc).__name__}: {exc}")

    result = []
    if success:
        result.append(f"✅ {route.get('title', title)} ongoing post published to {len(success)} channel(s):\n" + "\n".join(success))
    if failures:
        result.append("⚠️ Failed destinations:\n" + "\n".join(failures))
    return "\n\n".join(result) if result else "❌ No ongoing post was published. Check the bot's channel admin permissions."


@Client.on_message(filters.private & filters.command(["ongoing", "postongoing"]))
async def ongoing_command(client: Client, message: Message):
    if not is_admin_user(getattr(message, "from_user", None)):
        return await message.reply_text("⛔ Admin only.")
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].strip():
        return await message.reply_text("Usage: `/ongoing Anime Title`\n\nThe bot uses that anime's saved poster and invite links, plus the shared Main Ongoing Post Text.")
    try:
        result = await post_ongoing_anime(client, parts[1].strip())
    except Exception as exc:
        logger.exception("Unexpected failure while publishing ongoing post")
        result = f"⚠️ Ongoing post failed ({type(exc).__name__}). Check the bot logs and channel permissions."
    await message.reply_text(result[:3900], disable_web_page_preview=True, parse_mode=enums.ParseMode.DISABLED)
