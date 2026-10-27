"""Thumbnail and custom-caption commands."""

import logging
from pyrogram import Client, enums, filters
from helper.database import codeflixbots

logger = logging.getLogger(__name__)


@Client.on_message(filters.private & filters.command("set_caption"))
async def add_caption(client, message):
    if len(message.command) == 1:
        return await message.reply_text(
            "Send a caption after /set_caption. Supported placeholders: "
            "{filename}, {filesize}, {duration}.\n\n"
            "Example: /set_caption 📕 Name: {filename} | Size: {filesize} | Duration: {duration}"
        )
    caption = message.text.split(maxsplit=1)[1].strip()
    if not caption:
        return await message.reply_text("❌ Caption cannot be empty.")
    await codeflixbots.set_caption(message.from_user.id, caption=caption)
    await message.reply_text("✅ Your custom caption has been saved.")


@Client.on_message(filters.private & filters.command("del_caption"))
async def delete_caption(client, message):
    caption = await codeflixbots.get_caption(message.from_user.id)
    if not caption:
        return await message.reply_text("You don't have a custom caption saved.")
    await codeflixbots.set_caption(message.from_user.id, caption=None)
    await message.reply_text("✅ Custom caption deleted.")


@Client.on_message(filters.private & filters.command(["see_caption", "view_caption"]))
async def see_caption(client, message):
    caption = await codeflixbots.get_caption(message.from_user.id)
    if caption:
        await message.reply_text(f"Your custom caption:\n\n{caption}", parse_mode=enums.ParseMode.DISABLED)
    else:
        await message.reply_text("You don't have a custom caption saved.")


@Client.on_message(filters.private & filters.command(["view_thumb", "viewthumb"]))
async def viewthumb(client, message):
    thumb = await codeflixbots.get_thumbnail(message.from_user.id)
    if thumb:
        try:
            await client.send_photo(chat_id=message.chat.id, photo=thumb)
        except Exception:
            logger.exception("Could not send user's saved thumbnail")
            await message.reply_text("❌ Saved thumbnail could not be loaded. Set it again by sending a photo.")
    else:
        await message.reply_text("You don't have a saved thumbnail.")


@Client.on_message(filters.private & filters.command(["del_thumb", "delthumb"]))
async def removethumb(client, message):
    await codeflixbots.set_thumbnail(message.from_user.id, file_id=None)
    await message.reply_text("✅ Thumbnail deleted.")


@Client.on_message(filters.private & filters.photo)
async def addthumbs(client, message):
    try:
        await codeflixbots.set_thumbnail(message.from_user.id, file_id=message.photo.file_id)
        await message.reply_text("✅ Thumbnail saved successfully.")
    except Exception:
        logger.exception("Could not save thumbnail for user %s", message.from_user.id)
        await message.reply_text("❌ Couldn't save the thumbnail. Please try again.")
