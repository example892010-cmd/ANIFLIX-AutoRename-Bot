from config import Config, Txt
from helper.database import codeflixbots
from pyrogram.types import Message
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked, PeerIdInvalid
import os, sys, time, asyncio, logging, datetime
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ADMIN_USER_ID = Config.ADMIN

# Flag to indicate if the bot is restarting
is_restarting = False

@Client.on_message(filters.private & filters.command("restart") & filters.user(ADMIN_USER_ID))
async def restart_bot(b, m):
    global is_restarting
    if not is_restarting:
        is_restarting = True
        await m.reply_text("**Restarting.....**")

        # Replace the running process after Telegram has received the reply.
        await asyncio.sleep(1)
        os.execl(sys.executable, sys.executable, *sys.argv)


@Client.on_message(filters.private & filters.command("tutorial"))
async def tutorial(bot: Client, message: Message):
    user_id = message.from_user.id
    format_template = await codeflixbots.get_format_template(user_id)
    text = Txt.FILE_NAME_TXT
    if format_template:
        text += f"\n\n<b>Your current format:</b> <code>{format_template}</code>"
    await message.reply_text(
        text=text,
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("• ᴀɴɪꜰʟɪx", url="https://t.me/ANIFLIXANIMETAMIL"),
             InlineKeyboardButton("• ᴛᴜᴛᴏʀɪᴀʟ", url="https://t.me/ANIFLIXANIMETAMIL")]
        ])
    )


@Client.on_message(filters.command(["stats", "status"]) & filters.user(Config.ADMIN))
async def get_stats(bot, message):
    total_users = await codeflixbots.total_users_count()
    uptime = time.strftime("%Hh%Mm%Ss", time.gmtime(time.time() - bot.uptime))    
    start_t = time.time()
    st = await message.reply('**Accessing The Details.....**')    
    end_t = time.time()
    time_taken_s = (end_t - start_t) * 1000
    await st.edit(text=f"**--Bot Status--** \n\n**⌚️ Bot Uptime :** {uptime} \n**🐌 Current Ping :** `{time_taken_s:.3f} ms` \n**👭 Total Users :** `{total_users}`")

@Client.on_message(filters.command("broadcast") & filters.user(Config.ADMIN) & filters.reply)
async def broadcast_handler(bot: Client, m: Message):
    if Config.LOG_CHANNEL is not None:
        try:
            await bot.send_message(
                Config.LOG_CHANNEL,
                f"{m.from_user.mention} ({m.from_user.id}) started a broadcast.",
            )
        except Exception:
            logger.exception("Could not send broadcast-start log")
    all_users = await codeflixbots.get_all_users()
    broadcast_msg = m.reply_to_message
    sts_msg = await m.reply_text("Broadcast Started..!") 
    done = 0
    failed = 0
    success = 0
    start_time = time.time()
    total_users = await codeflixbots.total_users_count()
    async for user in all_users:
        sts = await send_msg(user['_id'], broadcast_msg)
        if sts == 200:
           success += 1
        else:
           failed += 1
        if sts == 400:
           await codeflixbots.delete_user(user['_id'])
        done += 1
        if not done % 20:
           await sts_msg.edit(f"Broadcast In Progress: \n\nTotal Users {total_users} \nCompleted : {done} / {total_users}\nSuccess : {success}\nFailed : {failed}")
    completed_in = datetime.timedelta(seconds=int(time.time() - start_time))
    await sts_msg.edit(f"Bʀᴏᴀᴅᴄᴀꜱᴛ Cᴏᴍᴩʟᴇᴛᴇᴅ: \nCᴏᴍᴩʟᴇᴛᴇᴅ Iɴ `{completed_in}`.\n\nTotal Users {total_users}\nCompleted: {done} / {total_users}\nSuccess: {success}\nFailed: {failed}")
           
async def send_msg(user_id, message):
    try:
        await message.copy(chat_id=int(user_id))
        return 200
    except FloodWait as e:
        await asyncio.sleep(max(1, int(getattr(e, "value", 1))))
        return await send_msg(user_id, message)
    except InputUserDeactivated:
        logger.info(f"{user_id} : Deactivated")
        return 400
    except UserIsBlocked:
        logger.info(f"{user_id} : Blocked The Bot")
        return 400
    except PeerIdInvalid:
        logger.info(f"{user_id} : User ID Invalid")
        return 400
    except Exception as e:
        logger.error(f"{user_id} : {e}")
        return 500

# ---------------------------------------------------------------------------
# Persistent Telegram admin UI. User input is captured by the session handler
# (group -9) before any rename/media handlers can see it.
# ---------------------------------------------------------------------------
import html
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from pyrogram import enums
from pyrogram import StopPropagation
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from helper.auth import is_admin_user
from helper.file_names import normalize_anime_title
from plugins.force_subs import get_fsub_settings, save_fsub_settings

ADMIN_STATE_COLLECTION = "admin_sessions"
ROUTES_COLLECTION = "anime_routes"
INVITES_COLLECTION = "anime_invite_links"
ONGOING_CHANNELS_COLLECTION = "ongoing_channel_settings"
TEMPLATES_COLLECTION = "anime_templates"
POST_TEMPLATES_COLLECTION = "post_template_settings"
FSUB_COLLECTION = "fsub_settings"
MAX_ONGOING_CHANNELS = 6
MAX_FSUB_CHANNELS = 6
DEFAULT_ONGOING_BUTTONS_TEMPLATE = (
    "#b ✦ 𝗗𝗢𝗪𝗡𝗟𝗢𝗔𝗗 𝗡𝗢𝗪 ✦ - {anime_invite}\n"
    "#r 𖤓𝗔𝗡𝗜𝗠𝗘 𝗜𝗡𝗗𝗘𝗫 𝗧𝗔𝗠𝗜𝗟𖤓 - https://t.me/+qGiH-Zw3ydJjZjU1"
)
DEFAULT_ONGOING_CHANNEL_IDS = [
    -1003693662050,
    -1003528863118,
    -1003673371837,
    -1003332822042,
    -1004419091895,
    -1003991502387,
]


def _now_utc():
    return datetime.now(timezone.utc)


def _message_photo_file_id(message):
    """Return the largest Telegram photo file_id safely across Pyrogram photo shapes."""
    photo = getattr(message, "photo", None)
    if not photo:
        return None
    if isinstance(photo, (list, tuple)):
        photo = photo[-1] if photo else None
    return getattr(photo, "file_id", None) if photo else None


def _formatted_message_content(message: Message) -> str:
    """Return admin-authored text as HTML so bold/italic/links survive template storage."""
    for attr in ("caption", "text"):
        value = getattr(message, attr, None)
        if value:
            html_value = getattr(value, "html", None)
            return str(html_value if html_value is not None else value).strip()
    return ""


def _title_key(title: str) -> str:
    return normalize_anime_title((title or "").strip())


def _route_collection():
    return codeflixbots.codeflixbots[ROUTES_COLLECTION]


def _admin_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📺 Anime Channels", callback_data="adm:anime_channels"), InlineKeyboardButton("🔗 Anime Invite Links", callback_data="adm:invites")],
        [InlineKeyboardButton("🎬 Episode Manager", callback_data="adm:episode_manager"), InlineKeyboardButton("✅ Link Verification", callback_data="adm:verify_links")],
        [InlineKeyboardButton("📚 Templates", callback_data="adm:templates"), InlineKeyboardButton("📝 Post Text", callback_data="adm:post_customization")],
        [InlineKeyboardButton("🔘 Ongoing Buttons", callback_data="adm:ongoing_buttons")],
        [InlineKeyboardButton("📡 Ongoing Channels", callback_data="adm:ongoing_channels"), InlineKeyboardButton("🔒 Force Subscribe", callback_data="adm:fsub")],
        [InlineKeyboardButton("⚙️ Bot Settings", callback_data="adm:settings")],
        [InlineKeyboardButton("🚀 Publish Ongoing", callback_data="adm:publish_ongoing")],
    ])


def _menu_keyboard(menu: str):
    if menu == "anime_channels":
        rows = [
            [InlineKeyboardButton("➕ Add", callback_data="adm:route_add"), InlineKeyboardButton("✏️ Edit", callback_data="adm:route_edit")],
            [InlineKeyboardButton("➖ Remove Assignment", callback_data="adm:route_remove"), InlineKeyboardButton("📋 View", callback_data="adm:route_list")],
            [InlineKeyboardButton("🗑️ Clear All Added Channels", callback_data="adm:route_clear_all")],
        ]
    elif menu == "invites":
        rows = [
            [InlineKeyboardButton("➕ Add Links", callback_data="adm:invite_add"), InlineKeyboardButton("✏️ Edit Link", callback_data="adm:invite_edit")],
            [InlineKeyboardButton("➖ Remove Link", callback_data="adm:invite_remove"), InlineKeyboardButton("📋 View Links", callback_data="adm:invite_view")],
            [InlineKeyboardButton("🗑️ Clear All Links", callback_data="adm:invite_clear_all")],
        ]
    elif menu == "ongoing_channels":
        rows = [
            [InlineKeyboardButton("➕ Add Channel", callback_data="adm:oc_add"), InlineKeyboardButton("✏️ Edit Channel", callback_data="adm:oc_edit")],
            [InlineKeyboardButton("➖ Remove Channel", callback_data="adm:oc_remove"), InlineKeyboardButton("📋 View Channels", callback_data="adm:oc_list")],
            [InlineKeyboardButton("🎯 Assign to Anime", callback_data="adm:route_edit")],
        ]
    elif menu == "fsub":
        rows = [
            [InlineKeyboardButton("➕ Add Channel", callback_data="adm:fsub_add"), InlineKeyboardButton("✏️ Edit Channel", callback_data="adm:fsub_edit")],
            [InlineKeyboardButton("➖ Remove Channel", callback_data="adm:fsub_remove"), InlineKeyboardButton("📋 View Channels", callback_data="adm:fsub_list")],
            [InlineKeyboardButton("🔛 Enable / Disable", callback_data="adm:fsub_toggle")],
        ]
    elif menu == "episode_manager":
        rows = [
            [InlineKeyboardButton("📋 Episode Queue", callback_data="adm:queue")],
            [InlineKeyboardButton("🛠 Repair Episode Groups", callback_data="adm:repair")],
        ]
    elif menu == "settings":
        rows = [
            [InlineKeyboardButton("🔒 Force Subscribe", callback_data="adm:fsub")],
            [InlineKeyboardButton("📡 Ongoing Channels", callback_data="adm:ongoing_channels")],
        ]
    elif menu == "post_customization":
        rows = [
            [InlineKeyboardButton("✏️ Main Ongoing Post Text", callback_data="adm:main_ongoing_text")],
            [InlineKeyboardButton("✏️ Anime Post Text", callback_data="adm:anime_post_text")],
        ]
    elif menu == "ongoing_buttons":
        rows = [
            [InlineKeyboardButton("✏️ Edit / Add Buttons", callback_data="adm:ongoing_buttons_edit")],
            [InlineKeyboardButton("🔄 Refresh Template", callback_data="adm:ongoing_buttons_refresh")],
        ]
    elif menu == "templates":
        rows = [
            [InlineKeyboardButton("➕ Create Template", callback_data="adm:template_create"), InlineKeyboardButton("✏️ Edit Template", callback_data="adm:template_edit")],
            [InlineKeyboardButton("📋 View Templates", callback_data="adm:template_list")],
            [InlineKeyboardButton("✏️ Main Ongoing Post Text", callback_data="adm:main_ongoing_text")],
            [InlineKeyboardButton("✏️ Anime Post Text", callback_data="adm:anime_post_text")],
        ]
    else:
        rows = []
    rows.append([InlineKeyboardButton("⬅️ Admin Home", callback_data="adm:home")])
    return InlineKeyboardMarkup(rows)


async def _set_admin_state(user_id: int, stage: str, data: dict | None = None):
    await codeflixbots.codeflixbots[ADMIN_STATE_COLLECTION].update_one(
        {"_id": int(user_id)},
        {"$set": {"stage": stage, "data": data or {}, "updated_at": _now_utc()}},
        upsert=True,
    )


async def _get_admin_state(user_id: int):
    return await codeflixbots.codeflixbots[ADMIN_STATE_COLLECTION].find_one({"_id": int(user_id)})


async def _clear_admin_state(user_id: int):
    await codeflixbots.codeflixbots[ADMIN_STATE_COLLECTION].delete_one({"_id": int(user_id)})


async def _prompt(client, user_id: int, stage: str, text: str, data: dict | None = None):
    await _set_admin_state(user_id, stage, data)
    await client.send_message(
        chat_id=int(user_id), text=text + "\n\nSend /cancel to cancel this action.",
        parse_mode=enums.ParseMode.DISABLED,
    )


def _parse_targets(raw: str) -> list[str | int]:
    raw = (raw or "").strip()
    if not raw or raw == "-":
        return []
    values = []
    for part in raw.split(","):
        part = part.strip()
        if not part or part == "-":
            continue
        if part.lstrip("-").isdigit():
            values.append(int(part))
        else:
            values.append(part if part.startswith("@") else "@" + part)
    # stable uniqueness
    result = []
    seen = set()
    for value in values:
        key = str(value).casefold()
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


async def _resolve_channel(client, raw: str):
    value = (raw or "").strip()
    if not value or value == "-":
        return None
    if value.lstrip("-").isdigit():
        target = int(value)
    elif value.startswith(("https://t.me/", "http://t.me/")):
        parsed = urlparse(value)
        path = parsed.path.strip("/")
        if not path or path.startswith(("+", "joinchat/")):
            raise ValueError("Use the numeric private-channel ID for private channels; invite URLs are for joining, not channel lookup.")
        target = "@" + path.split("/", 1)[0]
    else:
        target = value if value.startswith("@") else "@" + value
    chat = await client.get_chat(target)
    username = getattr(chat, "username", None)
    stored_target = "@" + username if username else int(chat.id)
    return {"target": stored_target, "chat_id": int(chat.id), "title": getattr(chat, "title", None) or str(stored_target)}


async def _validate_post_rights(client, chat_id: int):
    me = await client.get_me()
    member = await client.get_chat_member(int(chat_id), int(me.id))
    status = str(getattr(member, "status", "")).casefold().split(".")[-1]
    if status not in {"administrator", "creator", "owner"}:
        raise ValueError("The bot must be an administrator in the target channel before it can post.")
    permissions = getattr(member, "privileges", None)
    if permissions is not None and not (getattr(permissions, "can_post_messages", True) or status in {"creator", "owner"}):
        raise ValueError("The bot administrator role does not have permission to post messages.")


async def _ensure_ongoing_channel_seed():
    collection = codeflixbots.codeflixbots[ONGOING_CHANNELS_COLLECTION]
    doc = await collection.find_one({"_id": "global"})
    if doc:
        return doc
    channels = [
        {"chat_id": chat_id, "title": f"Ongoing Channel {index}", "mode": "private", "active": True}
        for index, chat_id in enumerate(DEFAULT_ONGOING_CHANNEL_IDS, start=1)
    ]
    await collection.update_one(
        {"_id": "global"},
        {"$setOnInsert": {"channels": channels, "updated_at": _now_utc()}},
        upsert=True,
    )
    return await collection.find_one({"_id": "global"}) or {"channels": channels}


async def _save_route_targets(client, title: str, individual_raw: str, ongoing_raw: str):
    key = _title_key(title)
    if not key:
        raise ValueError("Anime title cannot be empty.")
    individual_info = await _resolve_channel(client, individual_raw) if individual_raw.strip() != "-" else None
    ongoing_targets = _parse_targets(ongoing_raw)
    if len(ongoing_targets) > MAX_ONGOING_CHANNELS:
        raise ValueError(f"Assign no more than {MAX_ONGOING_CHANNELS} ongoing channels to one anime.")
    ongoing_infos = []
    for target in ongoing_targets:
        info = await _resolve_channel(client, str(target))
        if info:
            ongoing_infos.append(info)
    if individual_info:
        await _validate_post_rights(client, individual_info["chat_id"])
    for info in ongoing_infos:
        await _validate_post_rights(client, info["chat_id"])

    fields = {"title": title.strip(), "title_key": key, "updated_at": _now_utc()}
    unset = {}
    if individual_info:
        fields["individual_channel"] = individual_info["target"]
    else:
        unset["individual_channel"] = ""
    if ongoing_infos:
        fields["ongoing_channels"] = [item["target"] for item in ongoing_infos]
        fields["ongoing_channel"] = ongoing_infos[0]["target"]  # backward compatibility
        fields["ongoing_channel_titles"] = [item["title"] for item in ongoing_infos]
    else:
        unset["ongoing_channels"] = ""
        unset["ongoing_channel"] = ""
        unset["ongoing_channel_titles"] = ""
    update = {"$set": fields, "$setOnInsert": {"created_at": _now_utc()}}
    if unset:
        update["$unset"] = unset
    await _route_collection().update_one({"title_key": key}, update, upsert=True)


async def _find_route(title: str):
    key = _title_key(title)
    if not key:
        return None
    collection = _route_collection()
    route = await collection.find_one({"title_key": key})
    if route:
        return route
    # Old entries may not have a normalized title_key; search by title without guessing fuzzy matches.
    return await collection.find_one({"title": {"$regex": "^" + re.escape(title.strip()) + "$", "$options": "i"}})


def _parse_invite_line(line: str):
    line = line.strip()
    if not line:
        return None
    if "|" in line:
        label, url = [part.strip() for part in line.split("|", 1)]
    else:
        match = re.match(r"^(.+?)\s+-\s+(https?://\S+)$", line)
        if not match:
            return None
        label, url = match.group(1).strip(), match.group(2).strip()
    if not label or len(label) > 60:
        raise ValueError("Each button name must be 1–60 characters.")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"Invalid URL for button {label!r}. Use a complete https:// link.")
    return {"label": label, "key": label.casefold(), "url": url}


async def _upsert_invite_links(title: str, rows: list[dict]):
    key = _title_key(title)
    if not key:
        raise ValueError("Anime title cannot be empty.")
    collection = codeflixbots.codeflixbots[INVITES_COLLECTION]
    doc = await collection.find_one({"_id": key}) or {"_id": key, "title": title.strip(), "links": []}
    links = list(doc.get("links") or [])
    updated = 0
    added = 0
    for row in rows:
        old_idx = next((i for i, item in enumerate(links) if str(item.get("key") or item.get("label", "")).casefold() == row["key"]), None)
        row["updated_at"] = _now_utc()
        if old_idx is None:
            row["created_at"] = _now_utc()
            links.append(row)
            added += 1
        else:
            row["created_at"] = links[old_idx].get("created_at", _now_utc())
            links[old_idx] = row
            updated += 1
    await collection.update_one(
        {"_id": key},
        {"$set": {"title": title.strip(), "title_key": key, "links": links, "updated_at": _now_utc()}, "$setOnInsert": {"created_at": _now_utc()}},
        upsert=True,
    )
    return added, updated


async def _list_routes_text():
    cursor = _route_collection().find({}).sort("title", 1).limit(100)
    lines = []
    async for route in cursor:
        ongoing = route.get("ongoing_channels") or ([route["ongoing_channel"]] if route.get("ongoing_channel") else [])
        lines.append(
            f"• {route.get('title', '(unknown)')}\n"
            f"  Anime Post: {route.get('individual_channel') or 'Not set'}\n"
            f"  Ongoing: {', '.join(map(str, ongoing)) if ongoing else 'Not set'}\n"
            f"  Poster: {'Saved' if route.get('poster_file_id') else 'Not set'}"
        )
    return "\n\n".join(lines) if lines else "No anime channel routes saved yet."


async def _get_invite_doc(title: str):
    key = _title_key(title)
    doc = await codeflixbots.codeflixbots[INVITES_COLLECTION].find_one({"_id": key})
    if doc:
        return doc
    return await codeflixbots.codeflixbots[INVITES_COLLECTION].find_one({"title_key": key})


async def _fsub_text():
    settings = await get_fsub_settings()
    status = "ENABLED" if settings.get("enabled") and settings.get("channels") else "DISABLED"
    lines = [f"🔒 Force Subscribe: {status} ({len(settings.get('channels') or [])}/{MAX_FSUB_CHANNELS})"]
    for index, channel in enumerate(settings.get("channels") or [], start=1):
        lines.append(
            f"{index}. {channel.get('title') or channel.get('chat_id')}\n"
            f"   ID: {channel.get('chat_id')} | Mode: {channel.get('mode', 'normal')}\n"
            f"   Join link: {channel.get('join_url') or 'Not set'}"
        )
    return "\n".join(lines)


async def _ongoing_channels_text():
    doc = await _ensure_ongoing_channel_seed()
    channels = doc.get("channels") or []
    lines = [f"📡 Ongoing Channels ({len(channels)}/{MAX_ONGOING_CHANNELS})"]
    for index, channel in enumerate(channels, start=1):
        lines.append(f"{index}. {channel.get('title') or channel.get('chat_id')} — {channel.get('chat_id')}")
    lines.append("\nThese channels are used automatically for ongoing posts when an anime has no specific ongoing destinations assigned. Anime-specific assignments take priority. The bot must be admin in every channel it posts to.")
    return "\n".join(lines)


async def _global_post_templates():
    collection = codeflixbots.codeflixbots[POST_TEMPLATES_COLLECTION]
    doc = await collection.find_one({"_id": "global"})
    return doc or {}


async def _saved_templates_text():
    cursor = codeflixbots.codeflixbots[TEMPLATES_COLLECTION].find({}).sort("title", 1).limit(100)
    lines = ["📚 Saved Anime Templates"]
    async for item in cursor:
        lines.append(f"• {item.get('title', '(unnamed)')} — {'Poster saved' if item.get('poster_file_id') else 'No poster'}")
    return "\n".join(lines) if len(lines) > 1 else "No templates saved yet. Tap Create Template to add one."


async def _ongoing_buttons_summary():
    settings = await codeflixbots.codeflixbots[POST_TEMPLATES_COLLECTION].find_one({"_id": "global"}) or {}
    template = settings.get("ongoing_buttons_template") or DEFAULT_ONGOING_BUTTONS_TEMPLATE
    return (
        "🔘 ONGOING POST BUTTONS\n\n"
        "Current template (shared by all ongoing channels):\n"
        f"{template}\n\n"
        "Color codes: #b = blue, #r = red, #g = green. One button per line, format: "
        "#b Button Name - URL. Use {anime_invite} for the selected anime's saved invite link."
    )


@Client.on_message(filters.private & filters.command("admin"))
async def admin_dashboard(client: Client, message: Message):
    if not is_admin_user(getattr(message, "from_user", None)):
        return await message.reply_text("⛔ Admin only.")
    await message.reply_text(
        "🍥 **ANIFLIX AUTO-RENAME BOT — ADMIN PANEL**\n\nChoose a section below.",
        reply_markup=_admin_main_keyboard(),
    )


@Client.on_message(filters.private & filters.command("cancel"))
async def cancel_admin_action(client: Client, message: Message):
    user = getattr(message, "from_user", None)
    if not is_admin_user(user):
        return
    await _clear_admin_state(user.id)
    await message.reply_text("✅ Current admin action cancelled.", reply_markup=_admin_main_keyboard())


@Client.on_message(filters.private, group=-9)
async def handle_admin_session_input(client: Client, message: Message):
    """Consume the next admin response in a guided UI flow, before rename handlers."""
    user = getattr(message, "from_user", None)
    if not is_admin_user(user):
        return
    try:
        session = await _get_admin_state(user.id)
    except Exception:
        logger.exception("Could not load admin UI state")
        return
    if not session or not session.get("stage"):
        return

    if re.match(r"^/cancel(?:@\w+)?(?:\s|$)", (message.text or "").strip(), re.IGNORECASE):
        await _clear_admin_state(user.id)
        await message.reply_text("✅ Current action cancelled.", reply_markup=_admin_main_keyboard())
        raise StopPropagation
    if (message.text or "").startswith("/"):
        await message.reply_text("You have an unfinished admin action. Finish it or send /cancel.")
        raise StopPropagation

    stage = session["stage"]
    data = session.get("data") or {}
    try:
        if stage == "route_add_title":
            title = (message.text or "").strip()
            if not title:
                raise ValueError("Send the anime title first.")
            await _set_admin_state(user.id, "route_add_forward", {"title": title})
            await message.reply_text(
                f"Now forward any message directly from the **{title}** anime channel.\n\n"
                "Make sure this bot is already an admin in that channel. Forward the original channel message (do not copy/paste it). Send /cancel to stop."
            )

        elif stage == "route_add_forward":
            title = (data.get("title") or "").strip()
            source_chat = getattr(message, "forward_from_chat", None)
            # Newer Pyrogram versions may expose forward_origin instead.
            origin = getattr(message, "forward_origin", None)
            if not source_chat and origin:
                source_chat = getattr(origin, "chat", None) or getattr(origin, "sender_chat", None)
            if not source_chat or getattr(source_chat, "type", None) not in {enums.ChatType.CHANNEL, "channel"}:
                raise ValueError("Please forward a message directly from the anime channel. Do not send a copied message or a private chat message.")
            chat_id = int(source_chat.id)
            try:
                member = await client.get_chat_member(chat_id, client.me.id)
                status = str(getattr(member, "status", "")).lower()
                if status not in {"administrator", "creator", "chatmemberstatus.administrator", "chatmemberstatus.owner"}:
                    raise ValueError("The bot must be an admin in that channel first. Add it as admin, then forward a channel message again.")
            except ValueError:
                raise
            except Exception as exc:
                raise ValueError("I could not verify that the bot is an admin in this channel. Add the bot as admin and try forwarding a message again.") from exc
            key = _title_key(title)
            existing = await _route_collection().find_one({"title_key": key}) or {}
            fields = {
                "title": title, "title_key": key,
                "individual_channel": chat_id,
                "individual_channel_title": getattr(source_chat, "title", None) or title,
                "updated_at": _now_utc(),
            }
            await _route_collection().update_one(
                {"title_key": key},
                {"$set": fields, "$setOnInsert": {"created_at": _now_utc()}},
                upsert=True,
            )
            await _clear_admin_state(user.id)
            await message.reply_text(
                f"✅ Anime channel added for **{title}**!\nChannel: {getattr(source_chat, 'title', None) or title}\nChannel ID: `{chat_id}`\n\n"
                "You can add another anime channel from Admin → Anime Channels.",
                reply_markup=_admin_main_keyboard(),
            )

        elif stage == "route_edit":
            parts = [part.strip() for part in (message.text or "").split("|", 2)]
            if len(parts) != 3 or not parts[0]:
                raise ValueError("Use: Anime Title | Individual Channel ID/@username/- | Ongoing Channel IDs/@usernames separated by commas/-. Use - to clear a destination.")
            await _save_route_targets(client, parts[0], parts[1], parts[2])
            await _clear_admin_state(user.id)
            await message.reply_text(
                f"✅ Channel assignment saved for {parts[0]}.\nAnime Post: {parts[1] or 'Not set'}\nOngoing destinations: {parts[2] or 'Not set'}",
                reply_markup=_admin_main_keyboard(),
            )

        elif stage == "route_remove":
            title = (message.text or "").strip()
            key = _title_key(title)
            if not key:
                raise ValueError("Send an anime title.")
            result = await _route_collection().update_one(
                {"title_key": key},
                {"$unset": {"individual_channel": "", "ongoing_channel": "", "ongoing_channels": "", "ongoing_channel_titles": ""}, "$set": {"updated_at": _now_utc()}},
            )
            await _clear_admin_state(user.id)
            await message.reply_text("✅ Channel assignments removed." if result.modified_count else "No matching anime channel assignment was found.", reply_markup=_admin_main_keyboard())

        elif stage == "template_create_name":
            title = (message.text or "").strip()
            if not title:
                raise ValueError("Send a non-empty template name, e.g. Naruto Shippuden.")
            key = _title_key(title)
            await _set_admin_state(user.id, "template_create_poster", {"title": title, "title_key": key})
            await message.reply_text(f"Send me the poster of the template: {title}. Send it as a photo.")

        elif stage == "template_create_poster":
            title, key = data.get("title", ""), data.get("title_key", "")
            if not message.photo:
                raise ValueError("Please send the template poster as a Telegram photo.")
            poster_id = _message_photo_file_id(message)
            await codeflixbots.codeflixbots[TEMPLATES_COLLECTION].update_one(
                {"_id": key},
                {"$set": {"title": title, "title_key": key, "poster_file_id": poster_id, "updated_at": _now_utc()}, "$setOnInsert": {"created_at": _now_utc()}},
                upsert=True,
            )
            # Keep the old route poster field populated for backward compatibility.
            await _route_collection().update_one(
                {"title_key": key},
                {"$set": {"title": title, "title_key": key, "poster_file_id": poster_id, "updated_at": _now_utc()}, "$setOnInsert": {"created_at": _now_utc()}},
                upsert=True,
            )
            await _clear_admin_state(user.id)
            await message.reply_text(f"✅ Template saved: {title}. Its poster will be selected automatically by anime name. The ongoing post text is shared globally.", reply_markup=_admin_main_keyboard())

        elif stage == "template_edit_name":
            title = (message.text or "").strip()
            key = _title_key(title)
            doc = await codeflixbots.codeflixbots[TEMPLATES_COLLECTION].find_one({"_id": key})
            if not doc:
                raise ValueError(f"No saved template named {title!r}. Use Templates → View Templates to see saved names.")
            await _set_admin_state(user.id, "template_edit_poster", {"title": doc.get("title") or title, "title_key": key})
            await message.reply_text(f"Send the new poster for {doc.get('title') or title}, or send KEEP to keep its current poster.")

        elif stage == "template_edit_poster":
            title, key = data.get("title", ""), data.get("title_key", "")
            if (message.text or "").strip().casefold() == "keep":
                await _clear_admin_state(user.id)
                await message.reply_text(f"✅ Kept the saved poster for {title}.", reply_markup=_admin_main_keyboard())
            elif message.photo:
                poster_id = _message_photo_file_id(message)
                await codeflixbots.codeflixbots[TEMPLATES_COLLECTION].update_one({"_id": key}, {"$set": {"poster_file_id": poster_id, "updated_at": _now_utc()}})
                await _route_collection().update_one({"title_key": key}, {"$set": {"poster_file_id": poster_id, "updated_at": _now_utc()}}, upsert=True)
                await _clear_admin_state(user.id)
                await message.reply_text(f"✅ Poster updated for {title}.", reply_markup=_admin_main_keyboard())
            else:
                raise ValueError("Send a poster photo or type KEEP.")

        elif stage == "ongoing_buttons_template":
            template = (message.text or message.caption or "").strip()
            if not template:
                raise ValueError("Send at least one button line, or use /cancel to leave without saving.")
            if len(template) > 6000:
                raise ValueError("Keep the button template under 6000 characters.")
            lines = [line.strip() for line in template.splitlines() if line.strip()]
            invalid = [line for line in lines if not re.match(r"^#[bgr]\s+.+?\s+-\s*.+$", line, re.IGNORECASE)]
            if invalid:
                raise ValueError("Invalid line format. Use one button per line, e.g. #b DOWNLOAD NOW - {anime_invite}. Color codes: #b, #r, #g.")
            await codeflixbots.codeflixbots[POST_TEMPLATES_COLLECTION].update_one(
                {"_id": "global"},
                {"$set": {"ongoing_buttons_template": "\n".join(lines), "updated_at": _now_utc()}, "$setOnInsert": {"created_at": _now_utc()}},
                upsert=True,
            )
            await _clear_admin_state(user.id)
            await message.reply_text("✅ Ongoing buttons template saved. It will be used for every ongoing-channel post. The Download Now button automatically uses that anime's saved invite link.", reply_markup=_admin_main_keyboard())

        elif stage in {"main_ongoing_text", "anime_post_text"}:
            template = _formatted_message_content(message)
            if not template:
                raise ValueError("Template text cannot be empty. Send the post text, either as text or as a photo caption.")
            if len(template) > 4000:
                raise ValueError("Keep the text template under 4000 characters.")
            field = "ongoing_template" if stage == "main_ongoing_text" else "anime_post_template"
            await codeflixbots.codeflixbots[POST_TEMPLATES_COLLECTION].update_one(
                {"_id": "global"},
                {"$set": {field: template, "updated_at": _now_utc()}, "$setOnInsert": {"created_at": _now_utc()}},
                upsert=True,
            )
            await _clear_admin_state(user.id)
            label = "Main Ongoing Post Text" if field == "ongoing_template" else "Anime Post Text"
            await message.reply_text(f"✅ {label} saved. This text template is shared across all anime; placeholders will be replaced automatically.", reply_markup=_admin_main_keyboard())

        elif stage == "anime_template_name":
            title = (message.text or "").strip()
            if not title:
                raise ValueError("Send a non-empty anime title.")
            await _set_admin_state(user.id, "anime_template_text", {"title": title, "title_key": _title_key(title)})
            await message.reply_text(
                f"Send the Anime Post template for **{title}**.\n\n"
                "Placeholders: `{anime}`, `{title}`, `{season}`, `{episode}`, `{episode_range}`, `{qualities}`, `{tag}`, `{status}`, `{audio}`.\n"
                "The bot adds the 480p / 720p / 1080p inline quality buttons automatically. HTML tags such as `<b>title</b>` are supported.",
                parse_mode=enums.ParseMode.MARKDOWN,
            )

        elif stage == "anime_template_text":
            template = _formatted_message_content(message)
            if not template:
                raise ValueError("Template text cannot be empty; send it as text.")
            if len(template) > 950:
                raise ValueError("Keep the template to 950 characters or fewer so quality buttons fit safely.")
            title = data["title"]
            await _route_collection().update_one(
                {"title_key": data["title_key"]},
                {"$set": {"title": title, "title_key": data["title_key"], "individual_template": template, "updated_at": _now_utc()}, "$setOnInsert": {"created_at": _now_utc()}},
                upsert=True,
            )
            await _clear_admin_state(user.id)
            await message.reply_text(f"✅ Anime Post template saved for {title}.", reply_markup=_admin_main_keyboard())

        elif stage == "ongoing_template_name":
            title = (message.text or "").strip()
            if not title:
                raise ValueError("Send a non-empty anime title.")
            await _set_admin_state(user.id, "ongoing_template_content", {"title": title, "title_key": _title_key(title)})
            await message.reply_text(
                f"Now send the Ongoing Post for **{title}** as a poster photo with caption, or send its caption as text.\n\n"
                "Placeholders: `{anime}`, `{title}`, `{season}`, `{episode_range}`, `{tag}`, `{status}`, `{qualities}`.\n"
                "If you send a poster without a caption, the bot will ask for the text next. HTML tags such as `<b>...</b>` are supported.",
                parse_mode=enums.ParseMode.MARKDOWN,
            )

        elif stage == "ongoing_template_content":
            title = data["title"]
            template = _formatted_message_content(message)
            photo_id = _message_photo_file_id(message) if message.photo else None
            if photo_id and not template:
                data["poster_file_id"] = photo_id
                await _set_admin_state(user.id, "ongoing_template_text_after_photo", data)
                await message.reply_text("✅ Poster received. Now send the ongoing post caption/template text.")
                raise StopPropagation
            if not template:
                raise ValueError("Send text, or a poster photo with a caption. A photo without a caption is okay as the first step.")
            await _save_ongoing_template(title, data["title_key"], template, photo_id or data.get("poster_file_id"))
            await _clear_admin_state(user.id)
            await message.reply_text(f"✅ Ongoing Post template" + (" and poster" if photo_id or data.get("poster_file_id") else "") + f" saved for {title}. Use /ongoing {title} to publish it.", reply_markup=_admin_main_keyboard())

        elif stage == "ongoing_template_text_after_photo":
            template = _formatted_message_content(message)
            if not template:
                raise ValueError("Send a non-empty caption/template.")
            await _save_ongoing_template(data["title"], data["title_key"], template, data.get("poster_file_id"))
            await _clear_admin_state(user.id)
            await message.reply_text(f"✅ Ongoing Post template and poster saved for {data['title']}. Use /ongoing {data['title']} to publish it.", reply_markup=_admin_main_keyboard())

        elif stage == "invite_add_title":
            title = (message.text or "").strip()
            if not title:
                raise ValueError("Send an anime title.")
            await _set_admin_state(user.id, "invite_add_links", {"title": title, "title_key": _title_key(title)})
            await message.reply_text(
                f"Send one or more invite links for {title}, one per line:\n"
                "`Button Name | https://t.me/+invite-link`\n\n"
                "You can also use `Button Name - https://...`. Existing buttons with the same name are updated.",
                parse_mode=enums.ParseMode.MARKDOWN,
            )

        elif stage == "invite_add_links":
            raw_text = (message.text or message.caption or "").strip()
            rows = []
            errors = []
            for line_number, line in enumerate(raw_text.splitlines(), start=1):
                if not line.strip():
                    continue
                try:
                    parsed = _parse_invite_line(line)
                    if not parsed:
                        errors.append(f"Line {line_number}: use Button Name | https://...")
                    else:
                        rows.append(parsed)
                except ValueError as exc:
                    errors.append(f"Line {line_number}: {exc}")
            if errors:
                raise ValueError("\n".join(errors))
            if not rows:
                raise ValueError("No valid invite links found.")
            added, updated = await _upsert_invite_links(data["title"], rows)
            await _clear_admin_state(user.id)
            await message.reply_text(f"✅ Invite links saved for {data['title']}. Added: {added}; updated: {updated}.", reply_markup=_admin_main_keyboard())

        elif stage == "invite_edit":
            parts = [part.strip() for part in (message.text or "").split("|", 3)]
            if len(parts) != 4:
                raise ValueError("Use: Anime Title | Existing Button Name | New Button Name | New URL")
            title, old_label, new_label, url = parts
            parsed = _parse_invite_line(f"{new_label} | {url}")
            doc = await _get_invite_doc(title)
            if not doc:
                raise ValueError("No invite links are saved for that anime.")
            links = list(doc.get("links") or [])
            index = next((i for i, item in enumerate(links) if str(item.get("key") or item.get("label", "")).casefold() == old_label.casefold()), None)
            if index is None:
                raise ValueError("That button name was not found. Use View Links to check the exact name.")
            parsed["created_at"] = links[index].get("created_at", _now_utc())
            parsed["updated_at"] = _now_utc()
            links[index] = parsed
            await codeflixbots.codeflixbots[INVITES_COLLECTION].update_one({"_id": doc.get("_id")}, {"$set": {"links": links, "updated_at": _now_utc()}})
            await _clear_admin_state(user.id)
            await message.reply_text(f"✅ Updated link '{old_label}' for {title}.", reply_markup=_admin_main_keyboard())

        elif stage == "invite_remove":
            parts = [part.strip() for part in (message.text or "").split("|", 1)]
            if len(parts) != 2 or not all(parts):
                raise ValueError("Use: Anime Title | Button Name (or ALL to remove every invite link for that anime)")
            title, label = parts
            doc = await _get_invite_doc(title)
            if not doc:
                raise ValueError("No invite links are saved for that anime.")
            if label.casefold() == "all":
                new_links = []
            else:
                new_links = [item for item in (doc.get("links") or []) if str(item.get("key") or item.get("label", "")).casefold() != label.casefold()]
                if len(new_links) == len(doc.get("links") or []):
                    raise ValueError("That button name was not found.")
            await codeflixbots.codeflixbots[INVITES_COLLECTION].update_one({"_id": doc.get("_id")}, {"$set": {"links": new_links, "updated_at": _now_utc()}})
            await _clear_admin_state(user.id)
            await message.reply_text(f"✅ Invite links updated for {title}. Remaining links: {len(new_links)}.", reply_markup=_admin_main_keyboard())

        elif stage == "invite_view":
            title = (message.text or "").strip()
            doc = await _get_invite_doc(title)
            await _clear_admin_state(user.id)
            if not doc or not doc.get("links"):
                text = f"No invite links saved for {title}."
            else:
                text = f"🔗 Saved invite links for {doc.get('title', title)}:\n\n" + "\n".join(f"• {row.get('label')}: {row.get('url')}" for row in doc["links"])
            await message.reply_text(text[:3900], disable_web_page_preview=True, reply_markup=_admin_main_keyboard())

        elif stage == "publish_ongoing":
            title = (message.text or "").strip()
            if not title:
                raise ValueError("Send an anime title, e.g. Naruto Shippuden.")
            await _clear_admin_state(user.id)
            from plugins.ongoing_posts import post_ongoing_anime
            result = await post_ongoing_anime(client, title)
            await message.reply_text(result, reply_markup=_admin_main_keyboard(), disable_web_page_preview=True)

        elif stage == "fsub_add":
            parts = [part.strip() for part in (message.text or "").split("|", 2)]
            if len(parts) != 3:
                raise ValueError("Use: Channel ID/@username | Join URL | normal or join_request")
            raw_channel, join_url, mode = parts
            mode = mode.casefold().replace("-", "_").replace(" ", "_")
            if mode in {"joinrequest", "request"}:
                mode = "join_request"
            if mode not in {"normal", "join_request"}:
                raise ValueError("Mode must be normal or join_request.")
            parsed = urlparse(join_url)
            if parsed.scheme != "https" or parsed.netloc.lower() not in {"t.me", "www.t.me"}:
                raise ValueError("Join URL must be an https://t.me/... link.")
            info = await _resolve_channel(client, raw_channel)
            if not info:
                raise ValueError("Enter a valid channel ID or @username.")
            try:
                bot_member = await client.get_chat_member(info["chat_id"], (await client.get_me()).id)
                bot_status = str(getattr(bot_member, "status", "")).casefold().split(".")[-1]
                if bot_status not in {"administrator", "creator", "owner"}:
                    raise ValueError("The bot must be an administrator in this channel so Telegram membership checks work reliably.")
            except ValueError:
                raise
            except Exception as exc:
                raise ValueError("The bot must be an administrator of that channel and able to check members before FSub is saved.") from exc
            settings = await get_fsub_settings()
            channels = list(settings.get("channels") or [])
            if len(channels) >= MAX_FSUB_CHANNELS:
                raise ValueError("All 6 FSub slots are used. Remove one before adding another.")
            channels.append({"chat_id": info["chat_id"], "title": info["title"], "join_url": join_url, "mode": mode})
            await save_fsub_settings({"enabled": True, "channels": channels})
            await _clear_admin_state(user.id)
            await message.reply_text(f"✅ Force Subscribe channel added ({len(channels)}/{MAX_FSUB_CHANNELS}). Mode: {mode}.", reply_markup=_admin_main_keyboard())

        elif stage == "fsub_edit_index":
            raw_index = (message.text or "").strip()
            if not raw_index.isdigit():
                raise ValueError("Send the channel slot number shown in the FSub list.")
            settings = await get_fsub_settings()
            index = int(raw_index) - 1
            if index < 0 or index >= len(settings.get("channels") or []):
                raise ValueError("That FSub slot does not exist.")
            await _set_admin_state(user.id, "fsub_edit_data", {"index": index})
            await message.reply_text("Send replacement settings: Channel ID/@username | Join URL | normal or join_request")

        elif stage == "fsub_edit_data":
            parts = [part.strip() for part in (message.text or "").split("|", 2)]
            if len(parts) != 3:
                raise ValueError("Use: Channel ID/@username | Join URL | normal or join_request")
            raw_channel, join_url, mode = parts
            mode = mode.casefold().replace("-", "_").replace(" ", "_")
            if mode in {"joinrequest", "request"}:
                mode = "join_request"
            if mode not in {"normal", "join_request"}:
                raise ValueError("Mode must be normal or join_request.")
            parsed = urlparse(join_url)
            if parsed.scheme != "https" or parsed.netloc.lower() not in {"t.me", "www.t.me"}:
                raise ValueError("Join URL must be an https://t.me/... link.")
            info = await _resolve_channel(client, raw_channel)
            if not info:
                raise ValueError("Invalid channel.")
            try:
                bot_member = await client.get_chat_member(info["chat_id"], (await client.get_me()).id)
                bot_status = str(getattr(getattr(bot_member, "status", ""), "value", getattr(bot_member, "status", ""))).casefold().split(".")[-1]
                if bot_status not in {"administrator", "creator", "owner"}:
                    raise ValueError("The bot must be an administrator in this channel so FSub membership checks work reliably.")
            except ValueError:
                raise
            except Exception as exc:
                raise ValueError("The bot must be an administrator of that channel and able to check members before FSub is saved.") from exc
            settings = await get_fsub_settings()
            channels = list(settings.get("channels") or [])
            index = int(data["index"])
            if index >= len(channels):
                raise ValueError("That channel slot no longer exists; please restart Edit.")
            channels[index] = {"chat_id": info["chat_id"], "title": info["title"], "join_url": join_url, "mode": mode}
            await save_fsub_settings({"enabled": bool(settings.get("enabled", True)), "channels": channels})
            await _clear_admin_state(user.id)
            await message.reply_text("✅ Force Subscribe channel updated.", reply_markup=_admin_main_keyboard())

        elif stage in {"fsub_remove_index", "oc_remove_index"}:
            raw_index = (message.text or "").strip()
            if not raw_index.isdigit():
                raise ValueError("Send a valid slot number.")
            index = int(raw_index) - 1
            if stage == "fsub_remove_index":
                settings = await get_fsub_settings()
                channels = list(settings.get("channels") or [])
                if index < 0 or index >= len(channels):
                    raise ValueError("That FSub slot does not exist.")
                removed = channels.pop(index)
                await save_fsub_settings({"enabled": bool(channels) and bool(settings.get("enabled", True)), "channels": channels})
                text = f"✅ Removed FSub channel: {removed.get('title') or removed.get('chat_id')}"
            else:
                doc = await _ensure_ongoing_channel_seed()
                channels = list(doc.get("channels") or [])
                if index < 0 or index >= len(channels):
                    raise ValueError("That ongoing-channel slot does not exist.")
                removed = channels.pop(index)
                await codeflixbots.codeflixbots[ONGOING_CHANNELS_COLLECTION].update_one({"_id": "global"}, {"$set": {"channels": channels, "updated_at": _now_utc()}})
                text = f"✅ Removed ongoing channel: {removed.get('title') or removed.get('chat_id')}"
            await _clear_admin_state(user.id)
            await message.reply_text(text, reply_markup=_admin_main_keyboard())

        elif stage == "oc_add":
            raw_channel = (message.text or "").strip()
            info = await _resolve_channel(client, raw_channel)
            if not info:
                raise ValueError("Send a channel ID or @username.")
            await _validate_post_rights(client, info["chat_id"])
            doc = await _ensure_ongoing_channel_seed()
            channels = list(doc.get("channels") or [])
            if len(channels) >= MAX_ONGOING_CHANNELS:
                raise ValueError("All six ongoing-channel slots are used. Remove one before adding another.")
            channels.append({"chat_id": info["target"], "title": info["title"], "mode": "public" if isinstance(info["target"], str) else "private", "active": True})
            await codeflixbots.codeflixbots[ONGOING_CHANNELS_COLLECTION].update_one({"_id": "global"}, {"$set": {"channels": channels, "updated_at": _now_utc()}})
            await _clear_admin_state(user.id)
            await message.reply_text(f"✅ Ongoing channel added ({len(channels)}/{MAX_ONGOING_CHANNELS}).", reply_markup=_admin_main_keyboard())

        elif stage == "oc_edit":
            parts = [part.strip() for part in (message.text or "").split("|", 1)]
            if len(parts) != 2 or not parts[0].isdigit():
                raise ValueError("Use: Slot Number | Replacement Channel ID or @username")
            doc = await _ensure_ongoing_channel_seed()
            channels = list(doc.get("channels") or [])
            index = int(parts[0]) - 1
            if index < 0 or index >= len(channels):
                raise ValueError("That ongoing-channel slot does not exist.")
            info = await _resolve_channel(client, parts[1])
            if not info:
                raise ValueError("Invalid channel.")
            await _validate_post_rights(client, info["chat_id"])
            channels[index] = {"chat_id": info["target"], "title": info["title"], "mode": "public" if isinstance(info["target"], str) else "private", "active": True}
            await codeflixbots.codeflixbots[ONGOING_CHANNELS_COLLECTION].update_one({"_id": "global"}, {"$set": {"channels": channels, "updated_at": _now_utc()}})
            await _clear_admin_state(user.id)
            await message.reply_text("✅ Ongoing channel updated.", reply_markup=_admin_main_keyboard())

        elif stage == "set_ongoing_details":
            parts = [part.strip() for part in (message.text or "").split("|", 5)]
            if len(parts) != 6 or not parts[0]:
                raise ValueError("Use: Anime | Season | Episode Range | Tag | Status | Qualities")
            title, season, episode_range, tag, status, qualities = parts
            key = _title_key(title)
            await _route_collection().update_one(
                {"title_key": key},
                {"$set": {"title": title, "title_key": key, "ongoing_details": {"season": season, "episode_range": episode_range, "tag": tag, "status": status, "qualities": qualities}, "updated_at": _now_utc()}, "$setOnInsert": {"created_at": _now_utc()}},
                upsert=True,
            )
            await _clear_admin_state(user.id)
            await message.reply_text(f"✅ Ongoing details saved for {title}. /ongoing {title} will use them.", reply_markup=_admin_main_keyboard())

        else:
            raise ValueError("Unknown or expired admin action. Reopen /admin and try again.")

    except StopPropagation:
        raise
    except Exception as exc:
        logger.exception("Admin UI action failed: %s", stage)
        # Keep the session active after validation errors so the admin can correct input.
        await message.reply_text(f"❌ {type(exc).__name__}: {exc}\n\nPlease correct the input, or send /cancel.", parse_mode=enums.ParseMode.DISABLED)
    raise StopPropagation


async def _save_ongoing_template(title: str, key: str, template: str, poster_file_id: str | None):
    details = {}
    # Parse values from a plain-text copy so stored HTML formatting doesn't leave
    # markup fragments (for example </b>) inside the reusable episode details.
    plain_template = html.unescape(re.sub(r"<[^>]*>", "", template))
    patterns = {
        "season": r"(?im)season\s*:\s*([^\n|]+)",
        "episode_range": r"(?im)episode\s*:\s*([^\n]+)",
        "status": r"(?im)status\s*:\s*([^\n]+)",
        "qualities": r"(?im)quality\s*:\s*([^\n]+)",
    }
    for field, pattern in patterns.items():
        match = re.search(pattern, plain_template)
        value = match.group(1).strip() if match else ""
        value = value.split("╰", 1)[0].strip()
        if field == "episode_range":
            value = re.sub(r"\s+#\w+.*$", "", value).strip()
        # Placeholders belong in the template; keep the data field blank to avoid storing braces as actual metadata.
        details[field] = "" if value.startswith("{") and value.endswith("}") else value
    details["tag"] = "#New" if "#New" in plain_template else ""
    fields = {"title": title, "title_key": key, "ongoing_template": template, "ongoing_details": details, "updated_at": _now_utc()}
    if poster_file_id:
        fields["poster_file_id"] = poster_file_id
    await _route_collection().update_one(
        {"title_key": key},
        {"$set": fields, "$setOnInsert": {"created_at": _now_utc()}},
        upsert=True,
    )


@Client.on_callback_query(filters.regex(r"^adm:"))
async def admin_panel_callback(client: Client, query: CallbackQuery):
    user = getattr(query, "from_user", None)
    if not is_admin_user(user):
        await query.answer("Admin only.", show_alert=True)
        return
    action = (query.data or "").partition(":")[2]
    await query.answer()
    if action == "home":
        try:
            await query.message.edit_text("🍥 **ANIFLIX AUTO-RENAME BOT — ADMIN PANEL**\n\nChoose a section below.", reply_markup=_admin_main_keyboard())
        except Exception:
            await query.message.reply_text("ANIFLIX Auto-Rename Bot — Admin Panel", reply_markup=_admin_main_keyboard())
    elif action in {"anime_channels", "invites", "ongoing_channels", "fsub", "episode_manager", "settings", "post_customization", "ongoing_buttons", "templates"}:
        titles = {
            "anime_channels": "📺 ANIME CHANNELS — Add, edit, remove, or view each anime's individual and ongoing destinations.",
            "invites": "🔗 ANIME INVITE LINKS — Manage the buttons used in manual ongoing posts.",
            "ongoing_channels": await _ongoing_channels_text(),
            "fsub": await _fsub_text(),
            "episode_manager": "🎬 EPISODE MANAGER — Inspect saved groups and repair legacy split groups.",
            "settings": "⚙️ BOT SETTINGS — Force Subscribe and channel configuration.",
            "post_customization": "📝 POST TEXT — Configure the shared Main Ongoing Post Text and shared Anime Post Text.",
            "ongoing_buttons": await _ongoing_buttons_summary(),
            "templates": await _saved_templates_text(),
        }
        keyboard_key = action if action in {"anime_channels", "invites", "ongoing_channels", "fsub", "episode_manager", "settings", "post_customization", "ongoing_buttons", "templates"} else "settings"
        try:
            await query.message.edit_text(titles[action], reply_markup=_menu_keyboard(keyboard_key), disable_web_page_preview=True)
        except Exception:
            await query.message.reply_text(titles[action], reply_markup=_menu_keyboard(keyboard_key), disable_web_page_preview=True)
    elif action == "route_add":
        await _prompt(client, user.id, "route_add_title", "Send the anime title first, e.g. Naruto Shippuden.")
    elif action == "route_clear_all":
        confirm_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Yes, Clear All Channels", callback_data="adm:route_clear_confirm"),
             InlineKeyboardButton("❌ Cancel", callback_data="adm:anime_channels")]
        ])
        warning = ("⚠️ **Clear ALL Added Anime Channels?**\n\nThis removes all saved anime channel assignments, including individual anime destinations and their route records. This cannot be undone. Invite links, ongoing-button templates, and the separate ongoing-channel list will remain.")
        try:
            await query.message.edit_text(warning, reply_markup=confirm_keyboard)
        except Exception:
            await client.send_message(user.id, warning, reply_markup=confirm_keyboard)
    elif action == "route_clear_confirm":
        result = await _route_collection().delete_many({})
        message_text = f"✅ Cleared all added anime channel assignments. Records removed: {result.deleted_count}."
        try:
            await query.message.edit_text(message_text, reply_markup=_menu_keyboard("anime_channels"))
        except Exception:
            await client.send_message(user.id, message_text, reply_markup=_menu_keyboard("anime_channels"))
    elif action == "route_edit":
        await _prompt(client, user.id, "route_edit", "Send: Anime Title | Individual Channel ID/@username/- | Ongoing Channel IDs/@usernames separated by commas/-. Use - to clear a destination.")
    elif action == "route_remove":
        await _prompt(client, user.id, "route_remove", "Send the anime title whose channel assignments you want to remove. Templates/poster are kept.")
    elif action == "route_list":
        await client.send_message(user.id, await _list_routes_text(), disable_web_page_preview=True)
    elif action == "invite_add":
        await _prompt(client, user.id, "invite_add_title", "Send the anime title to add invite links for.")
    elif action == "invite_edit":
        await _prompt(client, user.id, "invite_edit", "Send: Anime Title | Existing Button Name | New Button Name | New URL")
    elif action == "invite_remove":
        await _prompt(client, user.id, "invite_remove", "Send: Anime Title | Button Name (or ALL to remove all links for that anime).")
    elif action == "invite_view":
        await _prompt(client, user.id, "invite_view", "Send the anime title whose saved invite links you want to view.")
    elif action == "invite_clear_all":
        confirm_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Yes, Clear All", callback_data="adm:invite_clear_confirm"),
             InlineKeyboardButton("❌ Cancel", callback_data="adm:invites")]
        ])
        warning = (
            "⚠️ **Clear ALL Anime Invite Links?**\n\n"
            "This removes every saved invite link for every anime. This cannot be undone.\n\n"
            "Your anime channel assignments and ongoing-button template will not be deleted."
        )
        try:
            await query.message.edit_text(warning, reply_markup=confirm_keyboard)
        except Exception:
            await client.send_message(user.id, warning, reply_markup=confirm_keyboard)
    elif action == "invite_clear_confirm":
        result = await codeflixbots.codeflixbots[INVITES_COLLECTION].delete_many({})
        message_text = f"✅ Cleared all saved anime invite links. Anime records cleared: {result.deleted_count}."
        try:
            await query.message.edit_text(message_text, reply_markup=_menu_keyboard("invites"))
        except Exception:
            await client.send_message(user.id, message_text, reply_markup=_menu_keyboard("invites"))
    elif action in {"template_create"}:
        await _prompt(client, user.id, "template_create_name", "Send the template name exactly as the anime name, e.g. Naruto Shippuden.")
    elif action in {"template_edit"}:
        await _prompt(client, user.id, "template_edit_name", "Send the exact name of the saved template you want to edit.")
    elif action == "template_list":
        await client.send_message(user.id, await _saved_templates_text(), reply_markup=_menu_keyboard("templates"))
    elif action == "ongoing_buttons_refresh":
        text = await _ongoing_buttons_summary()
        try:
            await query.message.edit_text(text, reply_markup=_menu_keyboard("ongoing_buttons"), disable_web_page_preview=True)
        except Exception:
            await client.send_message(user.id, text, reply_markup=_menu_keyboard("ongoing_buttons"), disable_web_page_preview=True)
    elif action == "ongoing_buttons_edit":
        await _prompt(
            client, user.id, "ongoing_buttons_template",
            "Send the complete ongoing-button template, one button per line.\n\n"
            "#b ✦ 𝗗𝗢𝗪𝗡𝗟𝗢𝗔𝗗 𝗡𝗢𝗪 ✦ - {anime_invite}\n"
            "#r 𖤓𝗔𝗡𝗜𝗠𝗘 𝗜𝗡𝗗𝗘𝗫 𝗧𝗔𝗠𝗜𝗟𖤓 - https://t.me/+qGiH-Zw3ydJjZjU1\n\n"
            "Use #b for blue, #r for red, #g for green. {anime_invite} is replaced with the invite link saved for whichever anime is being posted. This template is shared by all ongoing channels."
        )
    elif action == "main_ongoing_text":
        await _prompt(client, user.id, "main_ongoing_text", "Send the shared Main Ongoing Post Text. This text is used for every anime; placeholders such as {title}, {season}, {episode_range}, {status}, and {qualities} are replaced automatically.")
    elif action in {"anime_post_text", "anime_post"}:
        await _prompt(client, user.id, "anime_post_text", "Send the shared text-only Anime Post template. No poster is used for Anime Posts. Placeholders: {anime}, {title}, {season}, {episode_range}, {qualities}.")
    elif action == "ongoing_post":
        await _prompt(client, user.id, "main_ongoing_text", "Send the shared Main Ongoing Post Text for all anime. Posters are saved separately in Templates under each anime name.")
    elif action == "publish_ongoing":
        await _prompt(client, user.id, "publish_ongoing", "Send the anime title to publish now, e.g. Naruto Shippuden. Saved invite links and its ongoing template will be used.")
    elif action == "set_ongoing_details":
        await _prompt(client, user.id, "set_ongoing_details", "Send: Anime | Season | Episode Range | Tag | Status | Qualities")
    elif action == "oc_add":
        await _prompt(client, user.id, "oc_add", "Send a channel ID or @username. The bot must be an admin with posting rights. Maximum 6 ongoing channels.")
    elif action == "oc_edit":
        await _prompt(client, user.id, "oc_edit", "Send: Slot Number | Replacement Channel ID or @username")
    elif action == "oc_remove":
        doc = await _ensure_ongoing_channel_seed()
        channels = list(doc.get("channels") or [])
        if not channels:
            await client.send_message(user.id, "No ongoing channels are configured.")
        else:
            await _prompt(client, user.id, "oc_remove_index", "Current ongoing channel slots:\n" + "\n".join(f"{i}. {c.get('title') or c.get('chat_id')} — {c.get('chat_id')}" for i, c in enumerate(channels, 1)) + "\n\nSend the slot number to remove.")
    elif action == "oc_list":
        await client.send_message(user.id, await _ongoing_channels_text())
    elif action == "fsub_add":
        settings = await get_fsub_settings()
        if len(settings.get("channels") or []) >= MAX_FSUB_CHANNELS:
            await client.send_message(user.id, "All 6 FSub slots are occupied. Remove one first.")
        else:
            await _prompt(client, user.id, "fsub_add", "Send: Channel ID/@username | Join URL | normal OR join_request\nFor a private channel use its numeric ID and its invite link.")
    elif action == "fsub_edit":
        settings = await get_fsub_settings()
        channels = list(settings.get("channels") or [])
        if not channels:
            await client.send_message(user.id, "No FSub channels configured yet. Use Add Channel.")
        else:
            await _prompt(client, user.id, "fsub_edit_index", "Current FSub slots:\n" + "\n".join(f"{i}. {c.get('title') or c.get('chat_id')} — {c.get('chat_id')} ({c.get('mode', 'normal')})" for i, c in enumerate(channels, 1)) + "\n\nSend the slot number to edit.")
    elif action == "fsub_remove":
        settings = await get_fsub_settings()
        channels = list(settings.get("channels") or [])
        if not channels:
            await client.send_message(user.id, "No FSub channels configured yet.")
        else:
            await _prompt(client, user.id, "fsub_remove_index", "Current FSub slots:\n" + "\n".join(f"{i}. {c.get('title') or c.get('chat_id')}" for i, c in enumerate(channels, 1)) + "\n\nSend the slot number to remove.")
    elif action == "fsub_list":
        await client.send_message(user.id, await _fsub_text(), disable_web_page_preview=True)
    elif action == "fsub_toggle":
        settings = await get_fsub_settings()
        channels = settings.get("channels") or []
        if not channels and not settings.get("enabled"):
            await client.send_message(user.id, "Add at least one Force Subscribe channel before enabling it.")
        else:
            enabled = not bool(settings.get("enabled"))
            await save_fsub_settings({"enabled": enabled, "channels": channels})
            await client.send_message(user.id, f"✅ Force Subscribe is now {'ENABLED' if enabled else 'DISABLED'}.")
    elif action == "verify_links":
        from plugins.episode_publisher import EXPECTED_QUALITIES, _quality_field, publish_ready_batch
        cursor = codeflixbots.codeflixbots["episode_batches"].find({"state": {"$nin": ["merged"]}}).sort("updated_at", -1).limit(100)
        checked = 0
        results = []
        async for batch in cursor:
            files = batch.get("files") or {}
            if not all(files.get(_quality_field(q)) for q in EXPECTED_QUALITIES):
                continue
            checked += 1
            result = await publish_ready_batch(client, batch)
            results.append(f"• {batch.get('title')} S{batch.get('season')}E{batch.get('episode')}: {result}")
        text = f"✅ Link verification scan finished. Complete groups checked: {checked}.\n\n" + ("\n".join(results[:12]) if results else "No complete three-quality groups were found.")
        await client.send_message(user.id, text[:3900], disable_web_page_preview=True)
    elif action == "queue":
        cursor = codeflixbots.codeflixbots["episode_batches"].find({"state": {"$ne": "merged"}}).sort("updated_at", -1).limit(20)
        lines = []
        async for batch in cursor:
            files = batch.get("files") or {}
            present = [q for q in ("480p", "720p", "1080p") if files.get("q" + q)]
            lines.append(f"• {batch.get('title')} S{batch.get('season')}E{batch.get('episode')} — {len(present)}/3 ({', '.join(present) or 'none'}) — {batch.get('state', 'collecting')}")
        await client.send_message(user.id, "\n".join(lines) if lines else "✅ No episode batches saved.")
    elif action == "repair":
        from plugins.episode_publisher import _find_or_merge_episode_batch, _STORE_PROCESS_LOCK, publish_ready_batch, EXPECTED_QUALITIES, _quality_field
        batches_col = codeflixbots.codeflixbots["episode_batches"]
        cursor = batches_col.find({"state": {"$nin": ["published", "merged"]}}).sort("updated_at", 1).limit(300)
        pending = await cursor.to_list(length=300)
        repaired = 0
        details = []
        async with _STORE_PROCESS_LOCK:
            for old in pending:
                batch, status = await _find_or_merge_episode_batch(batches_col, str(old.get("_id", "")), old.get("title", ""), old.get("title_key", ""), str(old.get("season", "")), str(old.get("episode", "")))
                if not batch or status == "published":
                    continue
                repaired += 1
                files = batch.get("files") or {}
                if all(files.get(_quality_field(q)) for q in EXPECTED_QUALITIES):
                    details.append(f"{batch.get('title')} S{batch.get('season')}E{batch.get('episode')}: {await publish_ready_batch(client, batch)}")
                else:
                    details.append(f"{batch.get('title')} S{batch.get('season')}E{batch.get('episode')}: waiting for {', '.join(q for q in EXPECTED_QUALITIES if not files.get(_quality_field(q)))}")
        await client.send_message(user.id, f"🛠 Repair scan checked {repaired} group(s).\n\n" + ("\n".join(details[:10]) if details else "No groups needed repair."))
    else:
        await query.answer("Unknown admin action.", show_alert=True)
