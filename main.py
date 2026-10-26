import os
import re
import json
import logging
import tempfile
import threading
from pathlib import Path

from flask import Flask, jsonify
from PIL import Image
from mutagen import File as MutagenFile

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.error import TelegramError


# ============================================================
# CONFIGURATION
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

try:
    OWNER_ID = int(os.getenv("OWNER_ID", "0"))
except (TypeError, ValueError):
    OWNER_ID = 0

PORT = int(os.getenv("PORT", "10000"))

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

SETTINGS_FILE = DATA_DIR / "settings.json"
THUMBNAIL_FILE = DATA_DIR / "thumbnail.jpg"

DEFAULT_FORMAT = (
    "@ANIFLIXANIMETAMIL - {title} "
    "S{season} Ep{episode} [{quality}] [TAMIL]"
)

# Standard Telegram Bot API download limit.
MAX_DOWNLOAD_SIZE = 20 * 1024 * 1024


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger("aniflix_autorename")


# ============================================================
# WEB HEALTH CHECK FOR RENDER
# ============================================================

web = Flask(__name__)


@web.route("/")
def home():
    return "ANIFLIX Auto-Rename Bot is running!", 200


@web.route("/health")
def health():
    return jsonify({"status": "ok"}), 200


def run_web_server():
    web.run(
        host="0.0.0.0",
        port=PORT,
        debug=False,
        use_reloader=False,
    )


# ============================================================
# SETTINGS
# ============================================================

def load_settings():
    defaults = {
        "format": DEFAULT_FORMAT,
        "thumbnail": None,
        "metadata": False,
    }

    if not SETTINGS_FILE.exists():
        return defaults

    try:
        with SETTINGS_FILE.open("r", encoding="utf-8") as file:
            saved = json.load(file)

        if isinstance(saved, dict):
            defaults.update(saved)

    except (OSError, json.JSONDecodeError):
        logger.exception("Could not load settings; using defaults")

    if not isinstance(defaults.get("format"), str):
        defaults["format"] = DEFAULT_FORMAT

    if not isinstance(defaults.get("metadata"), bool):
        defaults["metadata"] = str(
            defaults.get("metadata", "")
        ).lower() in ("on", "true", "1", "yes")

    return defaults


settings = load_settings()


def save_settings():
    temporary_settings = SETTINGS_FILE.with_suffix(".tmp")

    with temporary_settings.open("w", encoding="utf-8") as file:
        json.dump(settings, file, indent=2, ensure_ascii=False)

    temporary_settings.replace(SETTINGS_FILE)


# ============================================================
# OWNER CHECK
# ============================================================

def is_owner(update: Update) -> bool:
    user = update.effective_user
    return bool(user and OWNER_ID and user.id == OWNER_ID)


async def reject_non_owner(update: Update) -> bool:
    if is_owner(update):
        return False

    message = update.effective_message
    if message:
        await message.reply_text("⛔ This is a private bot.")

    return True


# ============================================================
# FILENAME PARSING
# ============================================================

QUALITY_PATTERN = re.compile(
    r"(?i)\b(360p|480p|720p|1080p|1440p|2160p|4k|8k)\b"
)


def parse_filename(filename: str) -> dict:
    """
    Extract title, season, episode and quality from common names:
    Naruto Shippuden S01E02 [1080p].mkv
    Anime Season 2 Episode 5 720p.mp4
    Anime EP12 [480p].mkv
    """

    original = Path(filename.replace("\\", "/")).name
    stem = Path(original).stem

    season = ""
    episode = ""
    quality = ""

    quality_match = QUALITY_PATTERN.search(stem)
    if quality_match:
        quality = quality_match.group(1).lower()

    # Pattern: S01E02, S1 E2, S01_E02
    match = re.search(
        r"(?i)\bS(?:eason)?[\s._-]*(\d{1,2})"
        r"[\s._-]*E(?:p(?:isode)?)?[\s._-]*(\d{1,3})\b",
        stem,
    )

    if match:
        season = match.group(1)
        episode = match.group(2)
        stem = re.sub(match.re, " ", stem, count=1)

    else:
        # Pattern: Season 2 Episode 5
        match = re.search(
            r"(?i)\bSeason[\s._-]*(\d{1,2})"
            r"[\s._-]*Episode[\s._-]*(\d{1,3})\b",
            stem,
        )

        if match:
            season = match.group(1)
            episode = match.group(2)
            stem = re.sub(match.re, " ", stem, count=1)

        else:
            # Pattern: EP12 or Episode 12
            match = re.search(
                r"(?i)\b(?:EP|Episode)[\s._-]*(\d{1,3})\b",
                stem,
            )

            if match:
                episode = match.group(1)
                stem = re.sub(match.re, " ", stem, count=1)

    if quality:
        stem = QUALITY_PATTERN.sub(" ", stem)

    # Remove common release tags in square brackets.
    stem = re.sub(r"\[[^\]]*\]", " ", stem)

    # Clean common separators.
    stem = re.sub(r"[._]+", " ", stem)
    stem = re.sub(r"\s+", " ", stem)
    title = stem.strip(" -_.")

    if not title:
        title = Path(original).stem

    return {
        "title": title,
        "season": season,
        "episode": episode,
        "quality": quality,
    }


def build_filename(original_filename: str) -> str:
    parsed = parse_filename(original_filename)
    extension = Path(original_filename).suffix

    template = settings.get("format", DEFAULT_FORMAT)

    if not parsed["season"]:
        template = re.sub(
            r"(?i)\s*\bS(?:eason)?[\s._-]*\{season\}",
            "",
            template,
        )

    if not parsed["episode"]:
        template = re.sub(
            r"(?i)\s*\bEp(?:isode)?[\s._-]*\{episode\}",
            "",
            template,
        )

    new_name = template

    for key, value in parsed.items():
        new_name = new_name.replace(
            "{" + key + "}",
            str(value),
        )

    # Remove unsupported/unfilled placeholders.
    new_name = re.sub(r"\{[^{}]*\}", "", new_name)

    # Clean up empty season/episode tokens and empty brackets.
    new_name = re.sub(r"(?i)\bS\s+Ep\b", "", new_name)
    new_name = re.sub(r"(?i)\bS\s*$", "", new_name)
    new_name = re.sub(r"(?i)\bEp\s*(?=\[|$)", "", new_name)
    new_name = re.sub(r"\[\s*\]", "", new_name)

    # Prevent unsafe filename characters.
    new_name = re.sub(r'[\\/:*?"<>|]', "_", new_name)
    new_name = re.sub(r"\s+", " ", new_name).strip(" ._")

    if not new_name:
        new_name = parsed["title"] or "ANIFLIX"

    if extension:
        new_name += extension

    return new_name


# ============================================================
# OPTIONAL METADATA
# ============================================================

def apply_file_metadata(filepath: Path, title: str) -> None:
    """
    Add basic title/album/artist tags when the file format supports them.
    Unsupported formats are left unchanged.
    """

    try:
        audio = MutagenFile(str(filepath), easy=True)

        if audio is None:
            logger.info("Metadata unsupported for: %s", filepath.name)
            return

        if audio.tags is None:
            audio.add_tags()

        audio.tags["title"] = [title]
        audio.tags["album"] = ["ANIFLIX NETWORK TAMIL"]
        audio.tags["artist"] = ["ANIFLIX NETWORK TAMIL"]

        audio.save()
        logger.info("Metadata updated for %s", filepath.name)

    except Exception:
        logger.exception("Metadata could not be updated; continuing")


# ============================================================
# START / HELP
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if await reject_non_owner(update):
        return

    await update.effective_message.reply_text(
        "🍥 ANIFLIX AUTO-RENAME BOT 🍥\n\n"
        "Send a video or document to rename it.\n\n"
        "/format - View or change filename format\n"
        "/setthumb - Set thumbnail by replying to an image\n"
        "/viewthumb - Check thumbnail status\n"
        "/delthumb - Delete saved thumbnail\n"
        "/metadata - View metadata setting\n"
        "/setmetadata on - Enable metadata\n"
        "/setmetadata off - Disable metadata\n"
        "/resetmetadata - Disable metadata\n"
        "/help - Show commands"
    )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await start(update, context)


# ============================================================
# FILENAME FORMAT COMMAND
# ============================================================

async def format_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if await reject_non_owner(update):
        return

    message = update.effective_message

    if not context.args:
        await message.reply_text(
            "📝 Current filename format:\n\n"
            f"{settings['format']}\n\n"
            "To change it, send:\n"
            "/format {title} S{season} Ep{episode} [{quality}]\n\n"
            "Available placeholders:\n"
            "{title}  Anime title\n"
            "{season}  Season number\n"
            "{episode}  Episode number\n"
            "{quality}  Video quality\n\n"
            "Use /format reset to restore the default."
        )
        return

    value = " ".join(context.args).strip()

    if value.lower() == "reset":
        settings["format"] = DEFAULT_FORMAT
        save_settings()

        await message.reply_text(
            "✅ Filename format reset to default."
        )
        return

    if len(value) > 200:
        await message.reply_text(
            "❌ Format is too long. Please use fewer than 200 characters."
        )
        return

    settings["format"] = value
    save_settings()

    await message.reply_text(
        "✅ Filename format saved!\n\n"
        f"{value}"
    )


# ============================================================
# THUMBNAIL COMMANDS
# ============================================================

async def setthumb_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if await reject_non_owner(update):
        return

    message = update.effective_message
    replied = message.reply_to_message

    if not replied:
        await message.reply_text(
            "Reply to a photo or image document with /setthumb."
        )
        return

    file_id = None

    if replied.photo:
        file_id = replied.photo[-1].file_id

    elif (
        replied.document
        and replied.document.mime_type
        and replied.document.mime_type.startswith("image/")
    ):
        file_id = replied.document.file_id

    if not file_id:
        await message.reply_text(
            "❌ Please reply to a photo or an image file."
        )
        return

    temporary_image = DATA_DIR / "thumbnail_input.tmp"

    try:
        telegram_file = await context.bot.get_file(file_id)

        await telegram_file.download_to_drive(
            custom_path=str(temporary_image)
        )

        with Image.open(temporary_image) as image:
            image = image.convert("RGB")
            image.thumbnail((320, 320))
            image.save(
                THUMBNAIL_FILE,
                format="JPEG",
                quality=85,
                optimize=True,
            )

        settings["thumbnail"] = str(THUMBNAIL_FILE)
        save_settings()

        await message.reply_text("✅ Thumbnail saved successfully.")

    except Exception as exc:
        logger.exception("Could not save thumbnail")
        await message.reply_text(
            f"❌ Thumbnail failed: {type(exc).__name__}: {exc}"
        )

    finally:
        try:
            temporary_image.unlink(missing_ok=True)
        except OSError:
            pass


async def viewthumb_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if await reject_non_owner(update):
        return

    if THUMBNAIL_FILE.exists():
        await update.effective_message.reply_text(
            "✅ A thumbnail is saved."
        )
    else:
        await update.effective_message.reply_text(
            "ℹ️ No thumbnail saved. Reply to an image with /setthumb."
        )


async def delthumb_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if await reject_non_owner(update):
        return

    try:
        THUMBNAIL_FILE.unlink(missing_ok=True)
        settings["thumbnail"] = None
        save_settings()

        await update.effective_message.reply_text(
            "✅ Thumbnail deleted."
        )

    except OSError as exc:
        logger.exception("Could not delete thumbnail")
        await update.effective_message.reply_text(
            f"❌ Could not delete thumbnail: {exc}"
        )


# ============================================================
# METADATA COMMANDS
# ============================================================

async def metadata_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if await reject_non_owner(update):
        return

    state = "ON ✅" if settings.get("metadata") else "OFF ❌"

    await update.effective_message.reply_text(
        f"Metadata setting: {state}\n\n"
        "Enable: /setmetadata on\n"
        "Disable: /setmetadata off\n"
        "Reset: /resetmetadata"
    )


async def setmetadata_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if await reject_non_owner(update):
        return

    if not context.args:
        await update.effective_message.reply_text(
            "Use /setmetadata on or /setmetadata off."
        )
        return

    value = context.args[0].lower()

    if value in ("on", "true", "yes", "1"):
        settings["metadata"] = True
        save_settings()

        await update.effective_message.reply_text(
            "✅ Metadata enabled."
        )

    elif value in ("off", "false", "no", "0"):
        settings["metadata"] = False
        save_settings()

        await update.effective_message.reply_text(
            "✅ Metadata disabled."
        )

    else:
        await update.effective_message.reply_text(
            "Use /setmetadata on or /setmetadata off."
        )


async def resetmetadata_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if await reject_non_owner(update):
        return

    settings["metadata"] = False
    save_settings()

    await update.effective_message.reply_text(
        "✅ Metadata setting reset to OFF."
    )


# ============================================================
# FILE HANDLER
# ============================================================

async def handle_file(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message

    if not message or not is_owner(update):
        if message:
            await message.reply_text("⛔ This is a private bot.")
        return

    media = (
        message.document
        or message.video
        or message.audio
        or message.animation
    )

    if not media:
        return

    original_name = getattr(media, "file_name", None)

    if not original_name:
        if message.video or message.animation:
            original_name = "video.mp4"
        elif message.audio:
            original_name = "audio.mp3"
        else:
            original_name = "document.bin"

    # Avoid using any directory components from the supplied name.
    original_name = Path(
        original_name.replace("\\", "/")
    ).name

    file_size = int(getattr(media, "file_size", 0) or 0)

    if file_size > MAX_DOWNLOAD_SIZE:
        await message.reply_text(
            "❌ This file is larger than 20 MB.\n\n"
            "Telegram's standard Bot API cannot download files "
            "over 20 MB. This is a Telegram limit, not a filename "
            "formatting problem."
        )
        return

    status_message = None

    try:
        status_message = await message.reply_text(
            "⏳ Processing your file..."
        )

        with tempfile.TemporaryDirectory(
            prefix="aniflix_",
            dir=str(DATA_DIR),
        ) as temporary_directory:

            temp_dir = Path(temporary_directory)
            input_path = temp_dir / ("input" + Path(original_name).suffix)

            # Download the file from Telegram.
            telegram_file = await context.bot.get_file(media.file_id)

            await telegram_file.download_to_drive(
                custom_path=str(input_path)
            )

            # Build a clean output filename.
            output_name = build_filename(original_name)
            output_path = temp_dir / output_name

            # Metadata is optional and does not stop the rename if
            # the particular file format does not support metadata.
            if settings.get("metadata"):
                parsed = parse_filename(original_name)
                apply_file_metadata(input_path, parsed["title"])

            # Move/rename the downloaded file.
            input_path.replace(output_path)

            # Upload the renamed file to the owner's chat.
            if THUMBNAIL_FILE.exists():
                with (
                    output_path.open("rb") as document_file,
                    THUMBNAIL_FILE.open("rb") as thumbnail_file,
                ):
                    await message.reply_document(
                        document=document_file,
                        filename=output_name,
                        thumbnail=thumbnail_file,
                    )
            else:
                with output_path.open("rb") as document_file:
                    await message.reply_document(
                        document=document_file,
                        filename=output_name,
                    )

        if status_message:
            try:
                await status_message.delete()
            except TelegramError:
                pass

        logger.info(
            "Successfully renamed file: %s -> %s",
            original_name,
            output_name,
        )

    except Exception as exc:
        logger.exception(
            "File processing failed for %s",
            original_name,
        )

        if status_message:
            try:
                await status_message.delete()
            except TelegramError:
                pass

        # Display the exception type so the next failure is easier
        # to diagnose from Telegram and Render logs.
        error_detail = f"{type(exc).__name__}: {exc}"
        if len(error_detail) > 300:
            error_detail = error_detail[:300] + "..."

        try:
            await message.reply_text(
                "❌ File processing failed.\n\n"
                f"Error: {error_detail}\n\n"
                "Check Render Logs for the full traceback."
            )
        except TelegramError:
            logger.exception("Could not send error message to Telegram")


# ============================================================
# MAIN
# ============================================================

def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is missing. Add it in Render Environment Variables."
        )

    if OWNER_ID <= 0:
        raise RuntimeError(
            "OWNER_ID is missing or invalid. Add your numeric Telegram user ID."
        )

    logger.info("Starting ANIFLIX Auto-Rename Bot")

    threading.Thread(
        target=run_web_server,
        daemon=True,
        name="health-server",
    ).start()

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("format", format_command))

    application.add_handler(CommandHandler("setthumb", setthumb_command))
    application.add_handler(CommandHandler("viewthumb", viewthumb_command))
    application.add_handler(CommandHandler("delthumb", delthumb_command))

    application.add_handler(CommandHandler("metadata", metadata_command))
    application.add_handler(
        CommandHandler("setmetadata", setmetadata_command)
    )
    application.add_handler(
        CommandHandler("resetmetadata", resetmetadata_command)
    )

    file_filter = (
        filters.Document.ALL
        | filters.VIDEO
        | filters.AUDIO
        | filters.ANIMATION
    )

    application.add_handler(
        MessageHandler(file_filter, handle_file)
    )

    application.run_polling(
        drop_pending_updates=False,
        allowed_updates=Update.ALL_TYPES,
    )


if __name__ == "__main__":
    main()