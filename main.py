import os

import re

import asyncio

import logging

from pathlib import Path

from flask import Flask

from threading import Thread

from telegram import Update

from telegram.ext import (

    Application,

    CommandHandler,

    MessageHandler,

    ContextTypes,

    filters,

)

# ── Configuration ──────────────────────────────────

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

OWNER_ID = int(os.getenv("OWNER_ID", "0"))

PORT = int(os.getenv("PORT", "10000"))

DATA_DIR = Path("data")

DATA_DIR.mkdir(exist_ok=True)

logging.basicConfig(

    format="%(asctime)s - %(levelname)s - %(message)s",

    level=logging.INFO,

)

logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

app = Flask(__name__)

# ── Persistent settings ─────────────────────────────

# Render's local filesystem may reset after a restart.

SETTINGS_FILE = DATA_DIR / "settings.txt"

settings = {

    "format": "{title}",

    "thumbnail": "",

    "metadata": "",

}

def load_settings():

    if SETTINGS_FILE.exists():

        try:

            lines = SETTINGS_FILE.read_text(encoding="utf-8").splitlines()

            if len(lines) >= 3:

                settings["format"] = lines[0] or "{title}"

                settings["thumbnail"] = lines[1]

                settings["metadata"] = lines[2]

        except OSError:

            logger.exception("Could not load settings")

def save_settings():

    try:

        SETTINGS_FILE.write_text(

            "\n".join([

                settings["format"],

                settings["thumbnail"],

                settings["metadata"],

            ]),

            encoding="utf-8",

        )

    except OSError:

        logger.exception("Could not save settings")

# ── Render health check ─────────────────────────────

@app.get("/")

def home():

    return "ANIFLIX Auto-Rename Bot is running!", 200

@app.get("/health")

def health():

    return {"status": "ok"}, 200

def run_web_server():

    app.run(host="0.0.0.0", port=PORT, use_reloader=False)

# ── Access control ───────────────────────────────────

async def owner_only(update: Update) -> bool:

    user = update.effective_user

    if user and user.id == OWNER_ID and OWNER_ID != 0:

        return True

    if update.effective_message:

        await update.effective_message.reply_text(

            "⛔ This bot is private."

        )

    return False

# ── Commands ────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await owner_only(update):

        return

    await update.effective_message.reply_text(

        "🍥 ANIFLIX AUTO-RENAME BOT\n\n"

        "Send me a video or document to rename it.\n\n"

        "/format - Set filename format\n"

        "/setthumb - Set thumbnail using a photo\n"

        "/viewthumb - View saved thumbnail\n"

        "/delthumb - Delete thumbnail setting\n"

        "/metadata - View metadata settings\n"

        "/setmetadata - Set metadata text\n"

        "/resetmetadata - Clear metadata text\n"

        "/help - Show commands"

    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await owner_only(update):

        return

    await update.effective_message.reply_text(

        "📌 FORMAT EXAMPLE\n"

        "/format {title} S{season} Ep{episode} [{quality}] [TAMIL]\n\n"

        "Available placeholders:\n"

        "{title} {season} {episode} {quality} {extension}\n\n"

        "Send a photo to set your thumbnail, then use /setthumb.\n"

        "Use /setmetadata followed by your metadata text.\n"

        "Send a video or document to rename it."

    )

async def set_format(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await owner_only(update):

        return

    new_format = " ".join(context.args).strip()

    if not new_format:

        await update.effective_message.reply_text(

            "Usage:\n/format {title} S{season} Ep{episode} [{quality}] [TAMIL]"

        )

        return

    allowed = {"title", "season", "episode", "quality", "extension"}

    placeholders = re.findall(r"\{([^{}]+)\}", new_format)

    unknown = [item for item in placeholders if item not in allowed]

    if unknown:

        await update.effective_message.reply_text(

            "❌ Unknown placeholder(s): " + ", ".join(unknown)

        )

        return

    settings["format"] = new_format

    save_settings()

    await update.effective_message.reply_text(

        f"✅ Format saved:\n{new_format}"

    )

async def set_thumbnail(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await owner_only(update):

        return

    photo = update.effective_message.reply_to_message

    if photo and photo.photo:

        settings["thumbnail"] = photo.photo[-1].file_id

        save_settings()

        await update.effective_message.reply_text("✅ Thumbnail saved!")

        return

    await update.effective_message.reply_text(

        "First send a photo, then reply to that photo with /setthumb."

    )

async def view_thumbnail(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await owner_only(update):

        return

    thumb_id = settings["thumbnail"]

    if not thumb_id:

        await update.effective_message.reply_text("No thumbnail saved.")

        return

    await update.effective_message.reply_photo(thumb_id)

async def delete_thumbnail(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await owner_only(update):

        return

    settings["thumbnail"] = ""

    save_settings()

    await update.effective_message.reply_text("✅ Thumbnail setting cleared.")

async def view_metadata(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await owner_only(update):

        return

    value = settings["metadata"] or "(not set)"

    await update.effective_message.reply_text(f"Metadata text:\n{value}")

async def set_metadata(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await owner_only(update):

        return

    value = " ".join(context.args).strip()

    if not value:

        await update.effective_message.reply_text(

            "Usage: /setmetadata Your metadata text"

        )

        return

    settings["metadata"] = value

    save_settings()

    await update.effective_message.reply_text("✅ Metadata text saved.")

async def reset_metadata(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await owner_only(update):

        return

    settings["metadata"] = ""

    save_settings()

    await update.effective_message.reply_text("✅ Metadata text cleared.")

# ── File renaming ───────────────────────────────────

def clean_filename(name: str) -> str:

    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", name)

    name = name.strip(" .")

    return (name or "renamed_file")[:180]

def build_filename(original_name: str) -> str:

    original = Path(original_name)

    extension = original.suffix

    title = original.stem

    values = {

        "title": title,

        "season": "",

        "episode": "",

        "quality": "",

        "extension": extension.lstrip("."),

    }

    try:

        filename = settings["format"].format_map(values).strip()

    except (KeyError, ValueError):

        filename = title

    filename = clean_filename(filename)

    if extension and not filename.lower().endswith(extension.lower()):

        filename += extension

    return filename

async def process_file(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await owner_only(update):

        return

    message = update.effective_message

    document = message.document

    video = message.video

    if not document and not video:

        return

    original_name = (

        document.file_name if document and document.file_name

        else video.file_name if video and video.file_name

        else f"video_{video.file_unique_id}.mp4" if video

        else f"file_{document.file_unique_id}"

    )

    new_name = build_filename(original_name)

    await message.reply_text("⏳ Processing your file...")

    try:

        file_obj = await context.bot.get_file(

            document.file_id if document else video.file_id

        )

        local_path = DATA_DIR / f"input_{update.update_id}"

        await file_obj.download_to_drive(custom_path=str(local_path))

        # Preserve the original bytes; this bot does not encode files.

        await message.reply_document(

            document=open(local_path, "rb"),

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

            "❌ Could not process this file. Please try a smaller file."

        )

    finally:

        try:

            if "local_path" in locals() and local_path.exists():

                local_path.unlink()

        except OSError:

            logger.warning("Could not remove temporary file")

# ── Start bot ───────────────────────────────────────

def main():

    if not BOT_TOKEN:

        raise RuntimeError("Please set BOT_TOKEN in Render environment variables.")

    if OWNER_ID == 0:

        raise RuntimeError("Please set OWNER_ID in Render environment variables.")

    load_settings()

    Thread(target=run_web_server, daemon=True).start()

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))

    application.add_handler(CommandHandler("help", help_command))

    application.add_handler(CommandHandler("format", set_format))

    application.add_handler(CommandHandler("setthumb", set_thumbnail))

    application.add_handler(CommandHandler("viewthumb", view_thumbnail))

    application.add_handler(CommandHandler("delthumb", delete_thumbnail))

    application.add_handler(CommandHandler("metadata", view_metadata))

    application.add_handler(CommandHandler("setmetadata", set_metadata))

    application.add_handler(CommandHandler("resetmetadata", reset_metadata))

    application.add_handler(

        MessageHandler(

            filters.VIDEO | filters.Document.ALL,

            process_file,

        )

    )

    logger.info("Starting ANIFLIX Auto-Rename Bot")

    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":

    main()