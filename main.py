import asyncio
import logging
import os
from pathlib import Path
from threading import Thread

from flask import Flask
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import load_config
from storage import load_settings, save_settings
from filename_parser import parse_filename
from filename_utils import build_filename
from thumbnail_utils import save_thumbnail_from_telegram, get_thumbnail_path, delete_thumbnail
from metadata_utils import apply_metadata
from file_utils import temporary_file, safe_file_size
from logger_utils import setup_logger

logger = setup_logger()
config = load_config()

BOT_TOKEN = config["bot_token"]
OWNER_ID = config["owner_id"]
PORT = config["port"]

settings = load_settings()
web = Flask(__name__)


@web.get("/")
def home():
    return "ANIFLIX Auto-Rename Bot is running!", 200


@web.get("/health")
def health():
    return {"status": "ok"}, 200


def run_web():
    web.run(host="0.0.0.0", port=PORT, use_reloader=False)


async def owner_only(update: Update) -> bool:
    user = update.effective_user
    if user and user.id == OWNER_ID:
        return True

    if update.effective_message:
        await update.effective_message.reply_text("⛔ This bot is private.")
    return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await owner_only(update):
        return

    await update.effective_message.reply_text(
        "🍥 ANIFLIX AUTO-RENAME BOT\n\n"
        "Send me a video or document to rename it.\n\n"
        "/format - Set filename format\n"
        "/setthumb - Save a thumbnail by replying to a photo\n"
        "/viewthumb - View the saved thumbnail\n"
        "/delthumb - Delete thumbnail\n"
        "/metadata - View metadata settings\n"
        "/setmetadata - Set metadata text\n"
        "/resetmetadata - Clear metadata\n"
        "/help - Help"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await owner_only(update):
        return

    await update.effective_message.reply_text(
        "FORMAT EXAMPLE:\n"
        "/format @ANIFLIXANIMETAMIL - {title} S{season} "
        "Ep{episode} [{quality}] [TAMIL]\n\n"
        "Placeholders: {title}, {season}, {episode}, "
        "{quality}, {extension}\n\n"
        "To set a thumbnail, send a photo and reply to it with /setthumb.\n"
        "Use /setmetadata followed by metadata lines."
    )


async def format_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await owner_only(update):
        return

    template = " ".join(context.args).strip()
    if not template:
        await update.effective_message.reply_text(
            "Current format:\n" + settings["format"] +
            "\n\nUsage:\n/format {title} S{season} Ep{episode} [{quality}] [TAMIL]"
        )
        return

    settings["format"] = template
    save_settings(settings)
    await update.effective_message.reply_text("✅ Format saved:\n" + template)


async def setthumb_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await owner_only(update):
        return

    message = update.effective_message
    reply = message.reply_to_message

    if not reply or not reply.photo:
        await message.reply_text(
            "Send a photo, then reply to that photo with /setthumb."
        )
        return

    try:
        await save_thumbnail_from_telegram(context.bot, reply.photo[-1].file_id)
        settings["thumbnail"] = reply.photo[-1].file_id
        save_settings(settings)
        await message.reply_text("✅ Thumbnail saved.")
    except Exception:
        logger.exception("Thumbnail save failed")
        await message.reply_text("❌ Couldn't save that thumbnail.")


async def viewthumb_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await owner_only(update):
        return

    thumb_id = settings.get("thumbnail", "")
    if not thumb_id:
        await update.effective_message.reply_text("No thumbnail saved.")
        return

    try:
        await update.effective_message.reply_photo(thumb_id)
    except Exception:
        await update.effective_message.reply_text(
            "❌ Saved thumbnail is unavailable. Set it again using /setthumb."
        )


async def delthumb_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await owner_only(update):
        return

    delete_thumbnail()
    settings["thumbnail"] = ""
    save_settings(settings)
    await update.effective_message.reply_text("✅ Thumbnail setting cleared.")


async def metadata_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await owner_only(update):
        return

    current = settings.get("metadata", "") or "(not set)"
    await update.effective_message.reply_text("Metadata settings:\n" + current)


async def setmetadata_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await owner_only(update):
        return

    value = " ".join(context.args).strip()
    if not value:
        await update.effective_message.reply_text(
            "Usage:\n/setmetadata title=My Anime artist=ANIFLIX"
        )
        return

    settings["metadata"] = value
    save_settings(settings)
    await update.effective_message.reply_text("✅ Metadata settings saved.")


async def resetmetadata_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await owner_only(update):
        return

    settings["metadata"] = ""
    save_settings(settings)
    await update.effective_message.reply_text("✅ Metadata settings cleared.")


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await owner_only(update):
        return

    message = update.effective_message
    media = message.document or message.video

    if not media:
        return

    original_name = getattr(media, "file_name", None) or "renamed_file.bin"
    parsed = parse_filename(original_name)

    # Use parsed details in the filename template.
    template = settings.get("format", "{title}")
    extension = Path(original_name).suffix
    values = {
        "title": parsed["title"],
        "season": parsed["season"],
        "episode": parsed["episode"],
        "quality": parsed["quality"],
        "extension": extension.lstrip("."),
    }

    # The builder extracts the original title itself, so construct from
    # the parsed title and then use a template with the original extension.
    source_name = parsed["title"] + extension
    new_name = build_filename(source_name, template)

    # Fill season/episode/quality based on the detected values.
    for key, value in values.items():
        new_name = new_name.replace("{" + key + "}", value)

    # Remove any placeholders that weren't resolved.
    import re
    new_name = re.sub(r"\{[^{}]*\}", "", new_name)
    new_name = re.sub(r"\s+", " ", new_name).strip()
    if extension and not new_name.lower().endswith(extension.lower()):
        new_name = new_name.rstrip(". ") + extension

    await message.reply_text("⏳ Renaming your file...")

    try:
        telegram_file = await context.bot.get_file(media.file_id)

        with temporary_file(suffix=extension) as temp_path:
            await telegram_file.download_to_drive(custom_path=str(temp_path))

            size = safe_file_size(temp_path)
            if size <= 0:
                await message.reply_text("❌ The downloaded file is empty.")
                return

            metadata_text = settings.get("metadata", "")
            if metadata_text:
                ok, result = apply_metadata(str(temp_path), metadata_text)
                if not ok:
                    logger.info("Metadata not applied: %s", result)

            # Telegram supports thumbnails for certain media types, but sending
            # as a document does not display a video thumbnail in every client.
            thumb_path = get_thumbnail_path()
            with open(temp_path, "rb") as file_handle:
                if thumb_path and Path(thumb_path).exists():
                    with open(thumb_path, "rb") as thumb_handle:
                        await message.reply_document(
                            document=file_handle,
                            filename=new_name,
                            thumbnail=thumb_handle,
                            caption=f"✅ Renamed successfully!\n📄 {new_name}",
                            read_timeout=300,
                            write_timeout=300,
                            connect_timeout=30,
                            pool_timeout=30,
                        )
                else:
                    await message.reply_document(
                        document=file_handle,
                        filename=new_name,
                        caption=f"✅ Renamed successfully!\n📄 {new_name}",
                        read_timeout=300,
                        write_timeout=300,
                        connect_timeout=30,
                        pool_timeout=30,
                    )

    except Exception:
        logger.exception("File processing failed")
        await message.reply_text(
            "❌ File processing failed. Check Render logs and try again."
        )


def main():
    Thread(target=run_web, daemon=True).start()

    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("format", format_command))
    application.add_handler(CommandHandler("setthumb", setthumb_command))
    application.add_handler(CommandHandler("viewthumb", viewthumb_command))
    application.add_handler(CommandHandler("delthumb", delthumb_command))
    application.add_handler(CommandHandler("metadata", metadata_command))
    application.add_handler(CommandHandler("setmetadata", setmetadata_command))
    application.add_handler(CommandHandler("resetmetadata", resetmetadata_command))
    application.add_handler(
        MessageHandler(filters.VIDEO | filters.Document.ALL, handle_file)
    )

    logger.info("Starting ANIFLIX Auto-Rename Bot")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
