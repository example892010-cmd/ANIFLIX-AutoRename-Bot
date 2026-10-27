"""File download, rename, optional metadata, thumbnail and upload handlers."""

import asyncio
import logging
import os
import re
import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path

from PIL import Image
from pyrogram import Client, enums, filters
from pyrogram.errors import FloodWait

from helper.database import codeflixbots
from helper.file_names import (
    extract_quality,
    extract_season_episode,
    format_caption,
    metadata_enabled,
    render_filename,
    source_basename,
)
from helper.utils import progress_for_pyrogram
from plugins.antinsfw import check_anti_nsfw

logger = logging.getLogger(__name__)

# Prevent accidentally handling the same Telegram file twice in a short interval.
renaming_operations: dict[str, datetime] = {}

VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v", ".ts", ".mpeg",
    ".mpg", ".wmv", ".flv", ".3gp", ".ogv", ".vob", ".mts", ".m2ts",
}
AUDIO_EXTENSIONS = {
    ".mp3", ".m4a", ".aac", ".flac", ".wav", ".ogg", ".opus", ".wma",
    ".alac", ".aiff",
}
METADATA_EXTENSIONS = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS
# Telegram video/audio media messages are most reliable with these formats.
SEND_VIDEO_EXTENSIONS = {".mp4"}
SEND_AUDIO_EXTENSIONS = {".mp3", ".m4a"}


def extract_quality_compat(filename):
    """Compatibility wrapper kept for any local extensions importing this helper."""
    return extract_quality(filename)


async def process_thumbnail(thumb_path: str | None) -> str | None:
    """Create a Telegram-friendly JPEG thumbnail (maximum 320x320, under 200 KB)."""
    if not thumb_path or not os.path.isfile(thumb_path):
        return None

    try:
        with Image.open(thumb_path) as source:
            image = source.convert("RGB")
            image.thumbnail((320, 320))
            # Reduce JPEG quality as needed to stay under Telegram's thumbnail size limit.
            for quality in (88, 80, 72, 64, 56, 48):
                image.save(thumb_path, format="JPEG", quality=quality, optimize=True)
                if os.path.getsize(thumb_path) <= 190 * 1024:
                    return thumb_path
        logger.warning("Thumbnail was too large after compression; skipping it")
    except Exception:
        logger.exception("Thumbnail processing failed")
    return None


async def add_metadata(input_path: str, output_path: str, user_id: int) -> None:
    """Copy streams and set common metadata using FFmpeg, without re-encoding."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg is not installed or not on PATH")

    metadata = {
        "title": await codeflixbots.get_title(user_id),
        "artist": await codeflixbots.get_artist(user_id),
        "author": await codeflixbots.get_author(user_id),
        "video_title": await codeflixbots.get_video(user_id),
        "audio_title": await codeflixbots.get_audio(user_id),
        "subtitle": await codeflixbots.get_subtitle(user_id),
    }

    command = [
        ffmpeg,
        "-hide_banner",
        "-y",
        "-i", input_path,
        "-map", "0",
        "-c", "copy",
        "-metadata", f"title={metadata['title']}",
        "-metadata", f"artist={metadata['artist']}",
        "-metadata", f"author={metadata['author']}",
        "-metadata:s:v", f"title={metadata['video_title']}",
        "-metadata:s:a", f"title={metadata['audio_title']}",
        "-metadata:s:s", f"title={metadata['subtitle']}",
        "-loglevel", "error",
        output_path,
    ]

    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        try:
            error_text = stderr.decode("utf-8", errors="replace").strip()
        except AttributeError:
            error_text = str(stderr)
        raise RuntimeError(f"FFmpeg metadata operation failed: {error_text or 'unknown error'}")


async def _safe_edit(message, text: str) -> None:
    try:
        await message.edit_text(text, parse_mode=enums.ParseMode.DISABLED)
    except Exception:
        logger.debug("Could not update progress message", exc_info=True)


async def _get_thumbnail_path(client, message, user_id: int, work_dir: str) -> str | None:
    """Download the user's saved thumbnail, falling back to a video thumbnail."""
    path = os.path.join(work_dir, "thumbnail.jpg")
    try:
        saved_thumb = await codeflixbots.get_thumbnail(user_id)
        if saved_thumb:
            downloaded = await client.download_media(saved_thumb, file_name=path)
            return await process_thumbnail(downloaded)

        if message.video and getattr(message.video, "thumbs", None):
            thumbs = message.video.thumbs
            if thumbs:
                downloaded = await client.download_media(thumbs[0].file_id, file_name=path)
                return await process_thumbnail(downloaded)
    except Exception:
        logger.exception("Could not retrieve thumbnail; uploading without one")
    return None


@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def auto_rename_files(client, message):
    """Rename incoming private-chat media according to the user's saved template."""
    user = getattr(message, "from_user", None)
    if user is None:
        return
    user_id = user.id

    try:
        format_template = await codeflixbots.get_format_template(user_id)
    except Exception:
        logger.exception("Could not read rename format for user %s", user_id)
        return await message.reply_text("❌ Couldn't read your settings. Please try /start again.")

    if not format_template:
        return await message.reply_text("Please set a rename format using /autorename first.")

    if message.document:
        media = message.document
        media_type = "document"
    elif message.video:
        media = message.video
        media_type = "video"
    elif message.audio:
        media = message.audio
        media_type = "audio"
    else:
        return await message.reply_text("❌ Unsupported file type.")

    file_id = getattr(media, "file_id", None)
    if not file_id:
        return await message.reply_text("❌ Telegram did not provide a file ID for this message.")

    default_extension = ".mp4" if media_type == "video" else ".mp3" if media_type == "audio" else ".bin"
    original_name = source_basename(
        getattr(media, "file_name", None),
        fallback=f"file_{getattr(message, 'id', 'upload')}{default_extension}",
    )
    # Some Telegram documents have no filename extension. Add a safe fallback
    # so downstream upload/metadata tools can infer the file type where possible.
    if not Path(original_name).suffix:
        original_name = original_name.rstrip(" .") + default_extension

    # The checker sends its own reply when a blocked name is detected.
    try:
        if await check_anti_nsfw(original_name, message):
            return
    except Exception:
        logger.exception("Filename safety check failed; refusing this file")
        return await message.reply_text("❌ Filename validation failed. Please try another filename.")

    now = datetime.now()
    previous = renaming_operations.get(file_id)
    if previous and (now - previous).total_seconds() < 10:
        return
    renaming_operations[file_id] = now

    status = None
    try:
        new_filename = render_filename(original_name, format_template)
        extension = Path(original_name).suffix.lower()
        if not re.fullmatch(r"\.[a-z0-9]{1,10}", extension):
            extension = ""
        file_size = int(getattr(media, "file_size", 0) or 0)
        duration = getattr(media, "duration", None)
        status = await message.reply_text("⏬ Downloading file...")

        # Unique temp directory prevents collisions across concurrent uploads and keeps
        # user-provided filenames from escaping the temporary work area.
        with tempfile.TemporaryDirectory(prefix="autorename_") as work_dir:
            source_path = os.path.join(work_dir, f"source{extension}")
            downloaded_path = await client.download_media(
                message,
                file_name=source_path,
                progress=progress_for_pyrogram,
                progress_args=("Downloading...", status, time.time()),
            )
            if not downloaded_path or not os.path.isfile(downloaded_path):
                raise RuntimeError("Telegram download did not produce a file")

            current_path = downloaded_path
            meta_state = await codeflixbots.get_metadata(user_id)
            if metadata_enabled(meta_state) and extension in METADATA_EXTENSIONS:
                await _safe_edit(status, "🧩 Applying metadata...")
                metadata_path = os.path.join(work_dir, f"metadata{extension}")
                try:
                    await add_metadata(current_path, metadata_path, user_id)
                    if os.path.isfile(metadata_path) and os.path.getsize(metadata_path) > 0:
                        current_path = metadata_path
                except Exception:
                    # Metadata is optional: a metadata problem must not prevent a rename.
                    logger.exception("Metadata failed for %s; continuing with original file", original_name)
                    await _safe_edit(status, "⚠️ Metadata skipped; continuing with rename...")
            elif metadata_enabled(meta_state):
                logger.info("Metadata skipped for unsupported file extension %s", extension)

            output_path = os.path.join(work_dir, new_filename)
            if os.path.abspath(current_path) != os.path.abspath(output_path):
                # Both paths are in the same temporary directory, so an atomic rename
                # avoids a second full-size copy (important for large episodes).
                os.replace(current_path, output_path)

            caption_template = await codeflixbots.get_caption(user_id)
            caption = format_caption(caption_template, new_filename, file_size, duration)
            if len(caption) > 1024:
                caption = caption[:1021] + "..."
            thumbnail_path = await _get_thumbnail_path(client, message, user_id, work_dir)

            # Retain the incoming media type unless the user's /setmedia preference is
            # compatible with the actual file extension.
            preferred_type = (await codeflixbots.get_media_preference(user_id) or "").lower()
            upload_type = media_type
            if preferred_type == "document":
                upload_type = "document"
            elif preferred_type == "video" and extension in SEND_VIDEO_EXTENSIONS:
                upload_type = "video"
            elif preferred_type == "audio" and extension in SEND_AUDIO_EXTENSIONS:
                upload_type = "audio"

            # If an incoming message was mislabeled or has an unsupported media
            # extension, send it as a document rather than failing the upload.
            if upload_type == "video" and extension not in SEND_VIDEO_EXTENSIONS:
                upload_type = "document"
            elif upload_type == "audio" and extension not in SEND_AUDIO_EXTENSIONS:
                upload_type = "document"

            await _safe_edit(status, "⏫ Uploading renamed file...")
            upload_params = {
                "chat_id": message.chat.id,
                "caption": caption,
                "parse_mode": None,
                "progress": progress_for_pyrogram,
                "progress_args": ("Uploading...", status, time.time()),
            }
            if thumbnail_path:
                upload_params["thumb"] = thumbnail_path

            if upload_type == "video":
                await client.send_video(
                    video=output_path,
                    supports_streaming=extension == ".mp4",
                    **upload_params,
                )
            elif upload_type == "audio":
                await client.send_audio(audio=output_path, **upload_params)
            else:
                await client.send_document(document=output_path, **upload_params)

        await _safe_edit(status, "✅ Done! File renamed successfully.")
        logger.info("Renamed %s -> %s for user %s", original_name, new_filename, user_id)

    except FloodWait as exc:
        wait_seconds = int(getattr(exc, "value", 1))
        logger.warning("Flood wait while processing for user %s: %s seconds", user_id, wait_seconds)
        if status:
            await _safe_edit(status, f"⏳ Telegram rate limit. Please try again in {wait_seconds} seconds.")
        else:
            await message.reply_text(f"⏳ Telegram rate limit. Please try again in {wait_seconds} seconds.")
    except Exception as exc:
        logger.exception("File processing failed for user %s (%s)", user_id, original_name)
        error_text = f"❌ File processing failed: {type(exc).__name__}: {exc}"
        if status:
            await _safe_edit(status, error_text[:3900])
        else:
            await message.reply_text(error_text[:3900], parse_mode=enums.ParseMode.DISABLED)
    finally:
        renaming_operations.pop(file_id, None)
