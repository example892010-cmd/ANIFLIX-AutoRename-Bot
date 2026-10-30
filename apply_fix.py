#!/usr/bin/env python3
"""Apply the ANIFLIX /batch1renamed dual-destination publishing fix.

Run from the extracted bot repository root:
    python apply_fix.py --check   # verify source anchors only
    python apply_fix.py          # apply the two-file fix (creates .bak backups)
"""
from __future__ import annotations

import argparse
from pathlib import Path

REPO_ROOT = Path.cwd()
FILE_RENAME = REPO_ROOT / "plugins" / "file_rename.py"
ONGOING_POSTS = REPO_ROOT / "plugins" / "ongoing_posts.py"

IMPORT_ANCHOR = "from plugins.channel_routing import resolve_ongoing_targets as _resolve_ongoing_targets_from_settings"
ONGOING_IMPORT = "from plugins.ongoing_posts import post_ongoing_anime as _post_ongoing_anime"

OLD_ONGOING_SIGNATURE = "async def post_ongoing_anime(client: Client, title: str) -> str:"
NEW_ONGOING_SIGNATURE = '''async def post_ongoing_anime(
    client: Client,
    title: str,
    season: str | None = None,
    episode_range: str | None = None,
) -> str:'''

OLD_ONGOING_VALUES = '''        "season": details.get("season") or "—",
        "episode_range": details.get("episode_range") or "—",
        "episode": details.get("episode_range") or "—",'''
NEW_ONGOING_VALUES = '''        "season": season if season is not None and str(season).strip() else (details.get("season") or "—"),
        "episode_range": episode_range if episode_range is not None and str(episode_range).strip() else (details.get("episode_range") or "—"),
        "episode": episode_range if episode_range is not None and str(episode_range).strip() else (details.get("episode_range") or "—"),'''

NEW_LINK_ONLY_FUNCTION = r'''async def _publish_batch1renamed_link(client, message, details: dict) -> None:
    """Publish an existing link to Anime Post and Ongoing without handling media."""
    title = str(details.get("title") or "").strip()
    title_key = normalize_anime_title(title)
    link = str(details.get("stored_link") or "").strip()
    routes = codeflixbots.codeflixbots["anime_routes"]
    route = await routes.find_one({"title_key": title_key}) if title_key else None
    if not route and title:
        route = await routes.find_one({"title": {"$regex": "^" + re.escape(title) + "$", "$options": "i"}})
    if not route:
        await message.reply_text(
            f"❌ No saved channel settings were found for {title}. Add it in Admin Panel → Anime Channels first."
        )
        return

    episode = str(details.get("episode_range") or "").strip()
    season = str(details.get("season") or "").strip()

    # Anime Post and Ongoing are intentionally isolated: a failure in one destination
    # must not prevent an attempt to publish to the other destination.
    anime_result = "❌ Anime Post was not published."
    try:
        if not route.get("individual_channel"):
            raise RuntimeError("No Anime Post channel is assigned to this anime")
        settings = await codeflixbots.codeflixbots["post_template_settings"].find_one({"_id": "global"}) or {}
        template = settings.get("batch1renamed_button_template") or DEFAULT_BATCH1RENAMED_BUTTON_TEMPLATE
        button_rows = _build_batch1renamed_button_rows(template, details, link)
        chat = await client.get_chat(route["individual_channel"])
        caption_template = settings.get("anime_post_template") or DEFAULT_INDIVIDUAL_TEMPLATE
        caption_values = {
            "title": title, "anime": title,
            "season": season,
            "episode": episode, "episode_range": episode,
            "qualities": "Stored link", "status": "ON", "audio": "Tamil Audio",
            "quality_480p": "", "quality_720p": "", "quality_1080p": "",
            "link_480p": "", "link_720p": "", "link_1080p": "",
        }
        caption = _safe_template(caption_template, caption_values)
        sent_id = await _send_ongoing_bot_api(client, int(chat.id), None, caption, button_rows)
        try:
            await codeflixbots.codeflixbots["renamed_link_posts"].insert_one({
                "user_id": int(message.from_user.id), "title": title, "title_key": title_key,
                "season": season, "episode": episode,
                "url": link, "channel_id": int(chat.id), "message_id": int(sent_id),
                "created_at": datetime.utcnow(),
            })
        except Exception:
            logger.exception("Anime Post sent but link-only history could not be saved")
        anime_result = (
            f"✅ Published to {getattr(chat, 'title', None) or route['individual_channel']}\n"
            f"🔘 Button: {button_rows[0][0]['text']}"
        )
    except Exception as exc:
        logger.exception("Link-only /batch1renamed Anime Post failed")
        anime_result = f"❌ Anime Post failed: {type(exc).__name__}: {exc}"

    try:
        ongoing_result = await _post_ongoing_anime(
            client,
            str(route.get("title") or title),
            season=season,
            episode_range=episode,
        )
    except Exception as exc:
        logger.exception("Link-only /batch1renamed Ongoing publication failed")
        ongoing_result = f"❌ Ongoing publication failed: {type(exc).__name__}: {exc}"

    await message.reply_text(
        f"🎬 {title} • Season {season} • Episode {episode}\n\n"
        f"📺 Anime Post:\n{anime_result}\n\n"
        f"📡 Ongoing:\n{ongoing_result}\n\n"
        "No media was downloaded or stored by this command.",
        disable_web_page_preview=True,
        parse_mode=enums.ParseMode.DISABLED,
    )
'''


def transform_file_rename(source: str) -> str:
    if ONGOING_IMPORT not in source:
        if IMPORT_ANCHOR not in source:
            raise ValueError("Could not find the channel-routing import anchor in plugins/file_rename.py")
        source = source.replace(IMPORT_ANCHOR, IMPORT_ANCHOR + "\n" + ONGOING_IMPORT, 1)

    start_marker = "async def _publish_batch1renamed_link(client, message, details: dict) -> None:"
    end_marker = "\n\nasync def _active_batch_task(user_id: int) -> dict | None:"
    start = source.find(start_marker)
    if start < 0:
        raise ValueError("Could not find _publish_batch1renamed_link in plugins/file_rename.py")
    end = source.find(end_marker, start)
    if end < 0:
        raise ValueError("Could not find the end of _publish_batch1renamed_link in plugins/file_rename.py")
    source = source[:start] + NEW_LINK_ONLY_FUNCTION + source[end:]
    return source


def transform_ongoing_posts(source: str) -> str:
    if OLD_ONGOING_SIGNATURE in source:
        source = source.replace(OLD_ONGOING_SIGNATURE, NEW_ONGOING_SIGNATURE, 1)
    elif NEW_ONGOING_SIGNATURE not in source:
        raise ValueError("Could not find post_ongoing_anime function signature in plugins/ongoing_posts.py")

    if OLD_ONGOING_VALUES in source:
        source = source.replace(OLD_ONGOING_VALUES, NEW_ONGOING_VALUES, 1)
    elif NEW_ONGOING_VALUES not in source:
        raise ValueError("Could not find ongoing caption values block in plugins/ongoing_posts.py")
    return source


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify both source files have expected patch anchors")
    args = parser.parse_args()

    if not FILE_RENAME.is_file() or not ONGOING_POSTS.is_file():
        parser.error("Run this script from the ANIFLIX-AutoRename-Bot repository root (plugins/ files not found).")

    file_rename_source = FILE_RENAME.read_text(encoding="utf-8")
    ongoing_source = ONGOING_POSTS.read_text(encoding="utf-8")
    new_file_rename = transform_file_rename(file_rename_source)
    new_ongoing = transform_ongoing_posts(ongoing_source)

    if args.check:
        print("✅ Both source files contain the expected patch anchors. No files changed.")
        return 0

    if new_file_rename != file_rename_source:
        backup = FILE_RENAME.with_suffix(FILE_RENAME.suffix + ".bak")
        if not backup.exists():
            backup.write_text(file_rename_source, encoding="utf-8")
        FILE_RENAME.write_text(new_file_rename, encoding="utf-8")
    if new_ongoing != ongoing_source:
        backup = ONGOING_POSTS.with_suffix(ONGOING_POSTS.suffix + ".bak")
        if not backup.exists():
            backup.write_text(ongoing_source, encoding="utf-8")
        ONGOING_POSTS.write_text(new_ongoing, encoding="utf-8")

    print("✅ Applied the /batch1renamed dual-destination publishing fix.")
    print("✅ Backups were created beside the edited files if they did not already exist.")
    print("Next: run python -m compileall -q plugins and your normal Render deployment checks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
