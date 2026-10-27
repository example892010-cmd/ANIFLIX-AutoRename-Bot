"""Store renamed files, group 480p/720p/1080p per episode, and publish safely.

Channel routing is configured by the bot owner with /setanimechannels. No episode
post is sent until all three qualities have been stored and checked in Telegram.
"""

import asyncio
import hashlib
import logging
import os
import secrets
from datetime import datetime
from typing import Any

from pyrogram import Client, enums, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import Config
from helper.database import codeflixbots
from helper.file_names import (
    canonical_quality,
    extract_quality,
    extract_season_episode,
    extract_title,
    normalize_anime_title,
)

logger = logging.getLogger(__name__)
EXPECTED_QUALITIES = ("480p", "720p", "1080p")
_BATCH_LOCKS: dict[str, asyncio.Lock] = {}

DEFAULT_INDIVIDUAL_TEMPLATE = (
    "⬡ {title} | Official Tamil Dub\n\n"
    "⬡ Quality : {qualities}\n\n"
    "⬡ Season : {season} | ⬡ Episode : {episode} 👇\n\n"
    "FOR MORE ANIMES @ANIFLIXANIMETAMIL"
)
DEFAULT_ONGOING_TEMPLATE = DEFAULT_INDIVIDUAL_TEMPLATE


def _now():
    return datetime.utcnow()


def _title_key(title: str) -> str:
    return normalize_anime_title(title)


def _batch_id(title_key: str, season: str, episode: str) -> str:
    raw = f"{title_key}|S{season}|E{episode}".casefold()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _quality_field(quality: str) -> str:
    return "q" + quality


def _safe_template(template: str, values: dict[str, Any]) -> str:
    """Interpolate only named values. Unknown placeholders become empty strings."""
    class SafeValues(dict):
        def __missing__(self, key):
            return ""

    try:
        rendered = str(template or DEFAULT_INDIVIDUAL_TEMPLATE).format_map(SafeValues(values))
    except (ValueError, TypeError, KeyError):
        rendered = DEFAULT_INDIVIDUAL_TEMPLATE.format_map(SafeValues(values))
    return rendered[:1024]


def _private_message_link(chat_id: int, message_id: int) -> str:
    # Telegram's /c/ form works for members of a private channel.
    internal_id = str(abs(int(chat_id)))
    if internal_id.startswith("100"):
        internal_id = internal_id[3:]
    return f"https://t.me/c/{internal_id}/{int(message_id)}"


def _storage_post_url(storage_chat, message_id: int) -> str:
    username = (getattr(storage_chat, "username", None) or "").strip().lstrip("@")
    if username:
        return f"https://t.me/{username}/{int(message_id)}"
    return _private_message_link(storage_chat.id, message_id)


def _media_from_message(message):
    if not message:
        return None
    return (
        getattr(message, "document", None)
        or getattr(message, "video", None)
        or getattr(message, "audio", None)
        or getattr(message, "animation", None)
        or getattr(message, "photo", None)
    )


def _link_summary(files: dict[str, Any]) -> str:
    return "\n".join(
        f"{q}: {files[_quality_field(q)]['url']}"
        for q in EXPECTED_QUALITIES
    )


def _buttons(files: dict[str, Any]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(q, url=files[_quality_field(q)]["url"])
        for q in EXPECTED_QUALITIES
    ]])


def _render_post(route: dict, mode: str, title: str, season: str, episode: str,
                 files: dict[str, Any]) -> str:
    links = {q: files[_quality_field(q)]["url"] for q in EXPECTED_QUALITIES}
    values = {
        "title": title,
        "season": season,
        "episode": episode,
        "qualities": " • ".join(EXPECTED_QUALITIES),
        "quality_480p": links["480p"],
        "quality_720p": links["720p"],
        "quality_1080p": links["1080p"],
        "link_480p": links["480p"],
        "link_720p": links["720p"],
        "link_1080p": links["1080p"],
        "audio": "Tamil Audio",
        "status": "Tamil Audio",
    }
    key = "individual_template" if mode == "individual" else "ongoing_template"
    fallback = DEFAULT_INDIVIDUAL_TEMPLATE if mode == "individual" else DEFAULT_ONGOING_TEMPLATE
    return _safe_template(route.get(key) or fallback, values)


async def _verify_batch_files(client, batch: dict) -> tuple[bool, str]:
    files = batch.get("files") or {}
    for quality in EXPECTED_QUALITIES:
        entry = files.get(_quality_field(quality))
        if not entry or not entry.get("storage_message_id") or not entry.get("storage_chat_id"):
            return False, f"Missing stored {quality} file details."
        if canonical_quality(entry.get("filename", "")) != quality:
            return False, f"The filename for the {quality} slot does not match that quality."
        entry_season, entry_episode = extract_season_episode(entry.get("filename", ""))
        if (not entry_season or not entry_episode
                or str(int(entry_season)) != str(batch.get("season"))
                or str(int(entry_episode)) != str(batch.get("episode"))):
            return False, f"The {quality} filename does not match the saved season/episode."
        if _title_key(extract_title(entry.get("filename", ""))) != batch.get("title_key"):
            return False, f"The {quality} filename does not match the saved anime title."
        try:
            stored_username = (entry.get("storage_chat_username") or "").strip()
            if stored_username:
                storage_target = stored_username if stored_username.startswith("@") else "@" + stored_username
                storage_chat = await client.get_chat(storage_target)
            else:
                storage_chat = await client.get_chat(int(entry["storage_chat_id"]))
            stored = await client.get_messages(
                chat_id=int(storage_chat.id),
                message_ids=int(entry["storage_message_id"]),
            )
        except Exception as exc:
            logger.exception("Unable to verify stored %s file", quality)
            return False, f"Could not verify the {quality} stored message ({type(exc).__name__})."
        stored_media = _media_from_message(stored)
        if not stored_media:
            return False, f"The stored {quality} message no longer contains a file."
        expected_unique_id = entry.get("file_unique_id")
        actual_unique_id = getattr(stored_media, "file_unique_id", None)
        if expected_unique_id and actual_unique_id and expected_unique_id != actual_unique_id:
            return False, f"The stored {quality} message points to a different Telegram file."
        # Store the resolved Telegram chat ID after peer resolution for retrieval across restarts.
        entry["storage_chat_id"] = int(storage_chat.id)
    unique_ids = [files[_quality_field(q)].get("file_unique_id") for q in EXPECTED_QUALITIES]
    if not all(unique_ids):
        return False, "Telegram did not provide a unique file ID for every quality; nothing was published."
    if len(set(unique_ids)) != len(EXPECTED_QUALITIES):
        return False, "Two or more quality slots point to the same Telegram file; nothing was published."
    return True, ""


async def _send_target(client, route: dict, batch: dict, mode: str) -> tuple[bool, str]:
    target_field = "individual_channel" if mode == "individual" else "ongoing_channel"
    target = route.get(target_field)
    if not target:
        return False, "not configured"

    target_key = f"{mode}:{target}"
    published = batch.get("published_targets") or {}
    if published.get(target_key):
        return True, "already published"

    chat = await client.get_chat(target)
    title = batch["title"]
    season = batch["season"]
    episode = batch["episode"]
    files = batch["files"]
    caption = _render_post(route, mode, title, season, episode, files)
    keyboard = _buttons(files)
    poster_file_id = route.get("poster_file_id") if mode == "ongoing" else None

    if poster_file_id:
        sent = await client.send_photo(
            chat_id=chat.id,
            photo=poster_file_id,
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

    # Write per-target success immediately so a later target failing cannot cause a duplicate.
    await codeflixbots.codeflixbots["episode_batches"].update_one(
        {"_id": batch["_id"]},
        {"$set": {
            f"published_targets.{target_key}": {
                "chat_id": int(chat.id),
                "message_id": int(sent.id),
                "published_at": _now(),
            },
            "updated_at": _now(),
        }},
    )
    logger.info("Published %s S%sE%s to %s as message %s", title, season, episode, target, sent.id)
    return True, "published"


async def _publish_ready_batch_locked(client, batch: dict) -> str:
    """Verify and publish a complete batch; caller holds its per-episode lock."""
    ok, why = await _verify_batch_files(client, batch)
    if not ok:
        await codeflixbots.codeflixbots["episode_batches"].update_one(
            {"_id": batch["_id"]},
            {"$set": {"state": "verification_failed", "last_error": why, "updated_at": _now()}},
        )
        return f"⚠️ Not published: {why}"

    # Only now, after every stored message has been re-read and checked, create the
    # File-Store style deep links. A click starts this bot and returns the selected file.
    bot_username = getattr(client, "username", None)
    if not bot_username:
        bot_username = getattr(await client.get_me(), "username", None)
    if not bot_username:
        return "⚠️ Files are stored and verified, but the bot username could not be resolved; no links were generated."
    bot_username = str(bot_username).lstrip("@")
    files = batch.get("files") or {}
    for quality in EXPECTED_QUALITIES:
        entry = files[_quality_field(quality)]
        token = entry.get("access_token") or secrets.token_hex(8)
        access_url = f"https://t.me/{bot_username}?start=file_{token}"
        entry["access_token"] = token
        entry["url"] = access_url
        entry["storage_post_url"] = _storage_post_url(
            type("StoredChat", (), {"id": entry["storage_chat_id"], "username": entry.get("storage_chat_username")})(),
            int(entry["storage_message_id"]),
        )
        entry["verified_at"] = _now()
        await codeflixbots.codeflixbots["episode_batches"].update_one(
            {"_id": batch["_id"]},
            {"$set": {f"files.{_quality_field(quality)}": entry, "updated_at": _now()}},
        )
        await codeflixbots.codeflixbots["file_store"].update_one(
            {"storage_chat_id": int(entry["storage_chat_id"]),
             "storage_message_id": int(entry["storage_message_id"])},
            {"$set": {
                "access_token": token,
                "url": access_url,
                "storage_post_url": entry["storage_post_url"],
                "verified_at": _now(),
            }},
        )
        token_record = await codeflixbots.codeflixbots["file_store"].find_one({
            "access_token": token,
            "storage_chat_id": int(entry["storage_chat_id"]),
            "storage_message_id": int(entry["storage_message_id"]),
        })
        if not token_record or token_record.get("url") != access_url:
            return f"⚠️ {quality} was verified, but its access link could not be saved. Nothing was published."

    route = await codeflixbots.codeflixbots["anime_routes"].find_one(
        {"title_key": batch["title_key"]}
    )
    if not route:
        await codeflixbots.codeflixbots["episode_batches"].update_one(
            {"_id": batch["_id"]},
            {"$set": {"state": "ready_waiting_for_channel", "updated_at": _now()}},
        )
        return (
            "✅ All 3 files are stored and verified. Links are ready, but no channel mapping is configured for this anime yet.\n"
            "Use /setanimechannels to publish.\n\n" + _link_summary(files)
        )

    targets = [
        ("individual", route.get("individual_channel")),
        ("ongoing", route.get("ongoing_channel")),
    ]
    configured = [(mode, target) for mode, target in targets if target]
    if not configured:
        await codeflixbots.codeflixbots["episode_batches"].update_one(
            {"_id": batch["_id"]},
            {"$set": {"state": "ready_waiting_for_channel", "updated_at": _now()}},
        )
        return (
            "✅ All 3 files are stored and verified. No publish channel is configured; use /setanimechannels.\n\n"
            + _link_summary(files)
        )

    failures = []
    for mode, _target in configured:
        try:
            await _send_target(client, route, batch, mode)
        except Exception as exc:
            logger.exception("Could not publish %s post for batch %s", mode, batch["_id"])
            failures.append(f"{mode}: {type(exc).__name__}: {exc}")

    refreshed = await codeflixbots.codeflixbots["episode_batches"].find_one({"_id": batch["_id"]}) or batch
    published_targets = refreshed.get("published_targets") or {}
    all_done = all(
        published_targets.get(f"{mode}:{route[field]}")
        for mode, field in (("individual", "individual_channel"), ("ongoing", "ongoing_channel"))
        if route.get(field)
    )
    state = "published" if all_done and not failures else "publish_partial"
    await codeflixbots.codeflixbots["episode_batches"].update_one(
        {"_id": batch["_id"]},
        {"$set": {"state": state, "last_error": "\n".join(failures) if failures else None, "updated_at": _now()}},
    )
    if failures:
        return "⚠️ 3 files are stored, but one or more channel posts failed. No failed target is marked as published; check bot admin permissions and logs."
    return "✅ All 3 qualities stored and verified. Links generated and episode post(s) published."


async def publish_ready_batch(client, batch: dict) -> str:
    """Serialize publication per episode and reload current DB state before sending."""
    batch_id = str(batch.get("_id", ""))
    lock = _BATCH_LOCKS.setdefault(batch_id, asyncio.Lock())
    async with lock:
        current = await codeflixbots.codeflixbots["episode_batches"].find_one({"_id": batch_id})
        if not current:
            return "⚠️ Episode batch disappeared from MongoDB; nothing was published."
        if current.get("state") == "published":
            current_route = await codeflixbots.codeflixbots["anime_routes"].find_one(
                {"title_key": current.get("title_key")}
            ) or {}
            published_targets = current.get("published_targets") or {}
            has_unpublished_target = any(
                current_route.get(field)
                and not published_targets.get(f"{mode}:{current_route[field]}")
                for mode, field in (("individual", "individual_channel"), ("ongoing", "ongoing_channel"))
            )
            if not has_unpublished_target:
                return "✅ This episode has already been published; duplicate post prevented."
        current_files = current.get("files") or {}
        if not all(current_files.get(_quality_field(q)) for q in EXPECTED_QUALITIES):
            return "⏳ Waiting until 480p, 720p, and 1080p are all stored."
        return await _publish_ready_batch_locked(client, current)


async def store_file_and_process(client, sent_message, new_filename: str, user_id: int, file_size: int) -> str:
    """Copy a renamed file into storage, persist metadata, and process episode grouping."""
    storage_setting = os.environ.get("STORAGE_CHANNEL_ID", "").strip()
    fallback_username = os.environ.get("STORAGE_CHANNEL_USERNAME", "").strip()
    if not storage_setting:
        return "⚠️ Renaming succeeded, but File Store is not configured (STORAGE_CHANNEL_ID is missing)."

    storage_target: Any = storage_setting
    if storage_setting.lstrip("-").isdigit():
        storage_target = int(storage_setting)
    try:
        storage_chat = await client.get_chat(storage_target)
    except Exception:
        if fallback_username:
            storage_chat = await client.get_chat(fallback_username if fallback_username.startswith("@") else "@" + fallback_username)
        else:
            raise RuntimeError(
                "Cannot resolve STORAGE_CHANNEL_ID. For a public channel, set it to @ChannelUsername; "
                "optionally set STORAGE_CHANNEL_USERNAME as well."
            )

    stored_message = await client.copy_message(
        chat_id=storage_chat.id,
        from_chat_id=sent_message.chat.id,
        message_id=sent_message.id,
    )
    stored_media = _media_from_message(stored_message)
    if not stored_media:
        raise RuntimeError("Telegram copied the message, but the copied post contains no file")

    season, episode = extract_season_episode(new_filename)
    quality = canonical_quality(new_filename) or "Unknown"
    title = extract_title(new_filename)
    title_key = _title_key(title)
    created_at = _now()
    record = {
        "user_id": int(user_id),
        "storage_chat_id": int(storage_chat.id),
        "storage_chat_username": getattr(storage_chat, "username", None),
        "storage_message_id": int(stored_message.id),
        "filename": str(new_filename),
        "title": str(title),
        "title_key": title_key,
        "season": season,
        "episode": episode,
        "quality": quality,
        "url": None,
        "access_token": None,
        "storage_post_url": None,
        "file_id": getattr(stored_media, "file_id", None),
        "file_unique_id": getattr(stored_media, "file_unique_id", None),
        "file_size": int(getattr(stored_media, "file_size", file_size) or file_size),
        "created_at": created_at,
    }
    await codeflixbots.codeflixbots["file_store"].update_one(
        {"storage_chat_id": int(storage_chat.id), "storage_message_id": int(stored_message.id)},
        {"$set": record},
        upsert=True,
    )

    # An unidentifiable file stays safely stored but never gets attached to an episode.
    if not title_key or not season or not episode or quality not in EXPECTED_QUALITIES:
        missing = []
        if not title_key:
            missing.append("anime title")
        if not season:
            missing.append("season number")
        if not episode:
            missing.append("episode number")
        if quality not in EXPECTED_QUALITIES:
            missing.append("quality (480p/720p/1080p)")
        return (
            "✅ Renamed file saved to File Store.\n\n"
            "⚠️ No access link was generated and nothing was published because I could not reliably detect: "
            + ", ".join(missing) + "."
        )

    group_id = _batch_id(title_key, str(int(season)), str(int(episode)))
    quality_key = _quality_field(quality)
    group_file = {
        "quality": quality,
        "filename": str(new_filename),
        "url": None,
        "access_token": None,
        "storage_chat_id": int(storage_chat.id),
        "storage_chat_username": getattr(storage_chat, "username", None),
        "storage_message_id": int(stored_message.id),
        "file_id": getattr(stored_media, "file_id", None),
        "file_unique_id": getattr(stored_media, "file_unique_id", None),
        "file_size": record["file_size"],
        "verified_at": None,
    }
    batches = codeflixbots.codeflixbots["episode_batches"]
    existing = await batches.find_one({"_id": group_id})
    if existing and existing.get("state") == "published":
        return f"✅ File saved. This episode has already been published; duplicate {quality} was not published again."

    await batches.update_one(
        {"_id": group_id},
        {
            "$setOnInsert": {
                "title": title,
                "title_key": title_key,
                "season": str(int(season)),
                "episode": str(int(episode)),
                "created_at": created_at,
                "published_targets": {},
            },
            "$set": {
                f"files.{quality_key}": group_file,
                "state": "collecting",
                "updated_at": created_at,
                "last_error": None,
            },
        },
        upsert=True,
    )
    batch = await batches.find_one({"_id": group_id})
    files = batch.get("files") or {}
    missing_quality = [q for q in EXPECTED_QUALITIES if not files.get(_quality_field(q))]
    if missing_quality:
        return (
            f"✅ {quality} renamed and stored.\n\n"
            f"📺 {title} — Season {season}, Episode {episode}\n"
            f"Stored qualities: {3 - len(missing_quality)}/3\n"
            f"Waiting for: {', '.join(missing_quality)}"
        )

    # Re-read media from Telegram to ensure all three stored messages are present.
    result = await publish_ready_batch(client, batch)
    return result


# ---------- Owner-only channel and template configuration commands ----------

def _is_admin(message) -> bool:
    user = getattr(message, "from_user", None)
    if not user:
        return False
    allowed = set(Config.ADMIN or [])
    for name in ("OWNER_ID", "OWNERID", "ADMIN_ID"):
        raw = os.environ.get(name, "").strip()
        for item in raw.replace(",", " ").split() if raw else []:
            if item.isdigit():
                allowed.add(int(item))
    return int(user.id) in allowed


def _split_pipe_args(message, command_name: str, count: int):
    raw = (message.text or "").split(maxsplit=1)
    if len(raw) < 2:
        return None
    parts = [part.strip() for part in raw[1].split("|", count - 1)]
    if len(parts) != count or not parts[0]:
        return None
    return parts


@Client.on_message(filters.private & filters.command("setanimechannels"))
async def set_anime_channels(client, message):
    if not _is_admin(message):
        return await message.reply_text("⛔ Owner/admin only.")
    parts = _split_pipe_args(message, "setanimechannels", 3)
    if not parts:
        return await message.reply_text(
            "Usage:\n/setanimechannels Anime Title | @individual_channel | @ongoing_channel\n"
            "Use - for a channel you don't want to configure.\nExample:\n"
            "/setanimechannels Naruto Shippuden | @NarutoTamil | @NarutoOngoing"
        )
    title, individual, ongoing = parts
    individual = None if individual == "-" else individual
    ongoing = None if ongoing == "-" else ongoing
    if not individual and not ongoing:
        return await message.reply_text("❌ Set at least one channel.")

    # Validate destinations before saving. Invalid or inaccessible destinations are rejected.
    resolved = {"individual_channel": None, "ongoing_channel": None}
    try:
        for field, target in (("individual_channel", individual), ("ongoing_channel", ongoing)):
            if target:
                lookup_target = int(target) if target.lstrip("-").isdigit() else target
                if isinstance(lookup_target, str) and not lookup_target.startswith(("@", "https://t.me/", "http://t.me/")):
                    lookup_target = "@" + lookup_target
                chat = await client.get_chat(lookup_target)
                resolved[field] = ("@" + chat.username) if getattr(chat, "username", None) else int(chat.id)
    except Exception as exc:
        return await message.reply_text(
            f"❌ Could not access one of those channels: {type(exc).__name__}: {exc}\n"
            "Add the bot as an administrator with permission to post, then try again."
        )

    key = _title_key(title)
    await codeflixbots.codeflixbots["anime_routes"].update_one(
        {"title_key": key},
        {"$set": {"title": title, "title_key": key, **resolved, "updated_at": _now()},
         "$setOnInsert": {"created_at": _now()}},
        upsert=True,
    )
    await message.reply_text(
        f"✅ Channel route saved for {title}.\n"
        f"Individual: {individual or 'Not set'}\nOngoing: {ongoing or 'Not set'}\n\n"
        "I will publish only after 480p, 720p, and 1080p are stored and verified."
    )
    # Publish batches that were already complete while no route was configured.
    cursor = codeflixbots.codeflixbots["episode_batches"].find({"title_key": key})
    async for batch in cursor:
        files = batch.get("files") or {}
        if all(files.get(_quality_field(q)) for q in EXPECTED_QUALITIES):
            result = await publish_ready_batch(client, batch)
            await message.reply_text(f"{batch.get('title')} S{batch.get('season')}E{batch.get('episode')}:\n{result}")


@Client.on_message(filters.private & filters.command("setepisodetemplate"))
async def set_episode_template(client, message):
    if not _is_admin(message):
        return await message.reply_text("⛔ Owner/admin only.")
    parts = _split_pipe_args(message, "setepisodetemplate", 2)
    if not parts:
        return await message.reply_text(
            "Usage:\n/setepisodetemplate Anime Title | Your post text\n\n"
            "Placeholders: {title}, {season}, {episode}, {qualities}, {link_480p}, {link_720p}, {link_1080p}"
        )
    title, template = parts
    if len(template) > 950:
        return await message.reply_text("❌ Template must be 950 characters or shorter.")
    key = _title_key(title)
    result = await codeflixbots.codeflixbots["anime_routes"].update_one(
        {"title_key": key},
        {"$set": {"title": title, "title_key": key, "individual_template": template, "updated_at": _now()},
         "$setOnInsert": {"created_at": _now()}}, upsert=True,
    )
    await message.reply_text("✅ Individual episode template saved. Configure channels with /setanimechannels.")


@Client.on_message(filters.private & filters.command("setongoingtemplate"))
async def set_ongoing_template(client, message):
    if not _is_admin(message):
        return await message.reply_text("⛔ Owner/admin only.")
    parts = _split_pipe_args(message, "setongoingtemplate", 2)
    if not parts:
        return await message.reply_text(
            "Usage:\n/setongoingtemplate Anime Title | Your ongoing post text\n\n"
            "Placeholders: {title}, {season}, {episode}, {qualities}, {link_480p}, {link_720p}, {link_1080p}"
        )
    title, template = parts
    if len(template) > 950:
        return await message.reply_text("❌ Template must be 950 characters or shorter.")
    key = _title_key(title)
    await codeflixbots.codeflixbots["anime_routes"].update_one(
        {"title_key": key},
        {"$set": {"title": title, "title_key": key, "ongoing_template": template, "updated_at": _now()},
         "$setOnInsert": {"created_at": _now()}}, upsert=True,
    )
    await message.reply_text("✅ Ongoing post template saved.")


@Client.on_message(filters.private & filters.command("setanimeposter"))
async def set_anime_poster(client, message):
    if not _is_admin(message):
        return await message.reply_text("⛔ Owner/admin only.")
    raw = (message.text or "").split(maxsplit=1)
    if len(raw) < 2 or not message.reply_to_message or not message.reply_to_message.photo:
        return await message.reply_text(
            "Reply to an anime poster photo with:\n/setanimeposter Anime Title"
        )
    title = raw[1].strip()
    key = _title_key(title)
    photo = message.reply_to_message.photo
    await codeflixbots.codeflixbots["anime_routes"].update_one(
        {"title_key": key},
        {"$set": {"title": title, "title_key": key, "poster_file_id": photo.file_id, "updated_at": _now()},
         "$setOnInsert": {"created_at": _now()}}, upsert=True,
    )
    await message.reply_text(f"✅ Ongoing poster saved for {title}.")


@Client.on_message(filters.private & filters.command("listanimechannels"))
async def list_anime_channels(client, message):
    if not _is_admin(message):
        return await message.reply_text("⛔ Owner/admin only.")
    cursor = codeflixbots.codeflixbots["anime_routes"].find({}).sort("title", 1)
    lines = []
    async for route in cursor:
        lines.append(
            f"• {route.get('title', '(unknown)')}\n"
            f"  Individual: {route.get('individual_channel') or 'Not set'}\n"
            f"  Ongoing: {route.get('ongoing_channel') or 'Not set'}"
        )
    await message.reply_text("\n\n".join(lines) if lines else "No anime channel routes saved yet.")


@Client.on_message(filters.private & filters.command("episodequeue"))
async def show_episode_queue(client, message):
    if not _is_admin(message):
        return await message.reply_text("⛔ Owner/admin only.")
    cursor = codeflixbots.codeflixbots["episode_batches"].find(
        {"state": {"$ne": "published"}}
    ).sort("updated_at", -1).limit(20)
    lines = []
    async for batch in cursor:
        files = batch.get("files") or {}
        qualities = [q for q in EXPECTED_QUALITIES if files.get(_quality_field(q))]
        lines.append(
            f"• {batch.get('title')} S{batch.get('season')}E{batch.get('episode')} — "
            f"{len(qualities)}/3 ({', '.join(qualities) or 'none'}) — {batch.get('state', 'collecting')}"
        )
    await message.reply_text("\n".join(lines) if lines else "✅ No pending episode batches.")
