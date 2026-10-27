"""Start/help menus and miscellaneous commands."""

import asyncio
from html import escape
import logging

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

from config import Config, Txt
from helper.database import codeflixbots
from helper.auth import is_admin_user
from plugins.force_subs import check_fsub_membership, subscription_keyboard

logger = logging.getLogger(__name__)


def home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("• ᴍʏ ᴀʟʟ ᴄᴏᴍᴍᴀɴᴅs •", callback_data="help")],
        [
            InlineKeyboardButton("• ᴜᴘᴅᴀᴛᴇs", url="https://t.me/ANIFLIXANIMETAMIL"),
            InlineKeyboardButton("sᴜᴘᴘᴏʀᴛ •", url="https://t.me/anime_tamil_index_chat"),
        ],
        [
            InlineKeyboardButton("• ᴀʙᴏᴜᴛ", callback_data="about"),
            InlineKeyboardButton("sᴏᴜʀᴄᴇ •", callback_data="source"),
        ],
    ])


def help_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("• ᴀᴜᴛᴏ ʀᴇɴᴀᴍᴇ ғᴏʀᴍᴀᴛ •", callback_data="file_names")],
        [
            InlineKeyboardButton("• ᴛʜᴜᴍʙɴᴀɪʟ", callback_data="thumbnail"),
            InlineKeyboardButton("ᴄᴀᴘᴛɪᴏɴ •", callback_data="caption"),
        ],
        [
            InlineKeyboardButton("• ᴍᴇᴛᴀᴅᴀᴛᴀ", callback_data="meta"),
            InlineKeyboardButton("ᴅᴏɴᴀᴛᴇ •", callback_data="donate"),
        ],
        [InlineKeyboardButton("• ʜᴏᴍᴇ", callback_data="home")],
    ])


async def _edit_or_replace(query: CallbackQuery, text: str, reply_markup=None) -> None:
    """Edit a photo caption when the menu message has media; otherwise edit text."""
    message = query.message
    if message is None:
        return

    try:
        if message.media and message.caption is not None:
            await message.edit_caption(caption=text, reply_markup=reply_markup)
        else:
            await message.edit_text(
                text=text,
                disable_web_page_preview=True,
                reply_markup=reply_markup,
            )
    except Exception as exc:
        logger.debug("Menu edit failed; sending replacement: %s", exc)
        try:
            await message.reply_text(
                text=text,
                disable_web_page_preview=True,
                reply_markup=reply_markup,
            )
        except Exception:
            logger.exception("Could not display callback menu")


async def _answer(query: CallbackQuery, text: str = "") -> None:
    try:
        await query.answer(text)
    except Exception:
        logger.debug("Callback answer failed", exc_info=True)


async def _send_file_link_prompt(client: Client, user_id: int, token: str, missing, errors, prompt_message=None):
    if errors:
        text = (
            "⚠️ File access is temporarily blocked because the bot could not verify one or more "
            "subscription channels. Please contact the owner or try again later."
        )
        keyboard = None
    else:
        text = (
            "🔒 Join the required channel(s) below to access this file.\n\n"
            "After joining, tap **♻️ Try Again**. If a channel uses join requests, access is available "
            "after the request is approved."
        )
        keyboard = subscription_keyboard(missing, token)

    if prompt_message is not None:
        try:
            if prompt_message.media and prompt_message.caption is not None:
                await prompt_message.edit_caption(caption=text, reply_markup=keyboard)
            else:
                await prompt_message.edit_text(text, reply_markup=keyboard, disable_web_page_preview=True)
            return
        except Exception:
            logger.debug("Could not edit file access prompt; sending a new message", exc_info=True)
    await client.send_message(chat_id=int(user_id), text=text, reply_markup=keyboard, disable_web_page_preview=True)


async def _deliver_file_token(client: Client, user_id: int, token: str, prompt_message=None, callback_query=None) -> bool:
    """Verify FSub then deliver only the file matching a saved token."""
    if not token or len(token) > 60 or not all(ch.isalnum() or ch in "_-" for ch in token):
        text = "❌ This file link is invalid."
        if callback_query:
            await callback_query.answer("Invalid file link.", show_alert=True)
        await client.send_message(chat_id=int(user_id), text=text)
        return False

    try:
        if not is_admin_user(user_id):
            missing, errors = await check_fsub_membership(client, user_id)
            if missing or errors:
                if callback_query:
                    try:
                        await callback_query.answer("Please complete subscription verification.", show_alert=bool(errors))
                    except Exception:
                        pass
                await _send_file_link_prompt(client, user_id, token, missing, errors, prompt_message)
                return False
    except Exception:
        logger.exception("Could not verify FSub for user %s", user_id)
        if callback_query:
            try:
                await callback_query.answer("Membership check failed. Try again later.", show_alert=True)
            except Exception:
                pass
        await client.send_message(
            chat_id=int(user_id),
            text="⚠️ Membership verification failed. File access is blocked until the bot can verify the required channels.",
        )
        return False

    try:
        stored_record = await codeflixbots.codeflixbots["file_store"].find_one({"access_token": token})
    except Exception:
        logger.exception("File link lookup failed for user %s", user_id)
        await client.send_message(chat_id=int(user_id), text="⚠️ I couldn't access the file store. Please try again later.")
        return False
    if not stored_record:
        await client.send_message(chat_id=int(user_id), text="❌ File link not found or no longer available.")
        return False

    try:
        storage_username = (stored_record.get("storage_chat_username") or "").strip()
        if storage_username:
            storage_target = storage_username if storage_username.startswith("@") else "@" + storage_username
            storage_chat = await client.get_chat(storage_target)
        else:
            storage_chat = await client.get_chat(int(stored_record["storage_chat_id"]))
        stored_message = await client.get_messages(
            chat_id=storage_chat.id,
            message_ids=int(stored_record["storage_message_id"]),
        )
        stored_media = (
            getattr(stored_message, "document", None)
            or getattr(stored_message, "video", None)
            or getattr(stored_message, "audio", None)
            or getattr(stored_message, "animation", None)
            or getattr(stored_message, "photo", None)
        ) if stored_message else None
        if not stored_media:
            await client.send_message(chat_id=int(user_id), text="❌ The stored file is unavailable. Please contact the bot owner.")
            return False
        await client.copy_message(
            chat_id=int(user_id),
            from_chat_id=storage_chat.id,
            message_id=int(stored_record["storage_message_id"]),
        )
        logger.info("Delivered file-store token to user %s", user_id)
        if callback_query:
            try:
                await callback_query.answer("✅ Membership verified. File sent.")
            except Exception:
                pass
            if prompt_message is not None:
                try:
                    await prompt_message.edit_text("✅ Membership verified. Your requested file has been sent.", reply_markup=None)
                except Exception:
                    pass
        return True
    except Exception as exc:
        logger.exception("Could not deliver stored file to user %s", user_id)
        await client.send_message(
            chat_id=int(user_id),
            text=f"⚠️ I couldn't retrieve this file right now ({type(exc).__name__}). Please try again later.",
        )
        return False


@Client.on_message(filters.private & filters.command("start"))
async def start(client: Client, message: Message):
    user = message.from_user
    if user is None:
        return

    try:
        await codeflixbots.add_user(client, message)
    except Exception:
        logger.exception("Could not register user %s", user.id)
        await message.reply_text(
            "⚠️ I couldn't connect to the database. Please check the bot's MongoDB settings."
        )
        return

    start_parts = (message.text or "").split(maxsplit=1)
    payload = start_parts[1].strip() if len(start_parts) > 1 else ""
    if payload.startswith("file_"):
        await _deliver_file_token(client, user.id, payload[5:])
        return

    if not is_admin_user(user):
        return await message.reply_text(
            "🔒 This bot is for file access only. Open a quality button from an ANIFLIX post to get a file."
        )

    caption = Txt.START_TXT.format(user.mention)
    if Config.START_PIC:
        try:
            await message.reply_photo(
                photo=Config.START_PIC,
                caption=caption,
                reply_markup=home_keyboard(),
            )
            return
        except Exception:
            logger.exception("Start photo failed; falling back to text")

    await message.reply_text(
        text=caption,
        reply_markup=home_keyboard(),
        disable_web_page_preview=True,
    )


@Client.on_callback_query(filters.regex(r"^check_file_sub:"))
async def check_file_subscription_callback(client: Client, query: CallbackQuery):
    data = query.data or ""
    token = data.partition(":")[2]
    message = query.message
    if message is None:
        await query.answer("Please open the file link again.", show_alert=True)
        return
    await _deliver_file_token(client, query.from_user.id, token, prompt_message=message, callback_query=query)


@Client.on_callback_query(filters.regex(r"^(home|help|caption|meta|donate|file_names|thumbnail|source|premiumx|plans|about|close|close_data)$"))
async def cb_handler(client: Client, query: CallbackQuery):
    data = query.data or ""
    user_id = query.from_user.id

    if data == "home":
        await _answer(query)
        await _edit_or_replace(query, Txt.START_TXT.format(query.from_user.mention), home_keyboard())

    elif data == "help":
        await _answer(query)
        await _edit_or_replace(query, Txt.HELP_TXT.format(client.mention), help_keyboard())

    elif data == "caption":
        await _answer(query)
        await _edit_or_replace(
            query,
            Txt.CAPTION_TXT,
            InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("• sᴜᴘᴘᴏʀᴛ", url="https://t.me/anime_tamil_index_chat"),
                    InlineKeyboardButton("ʙᴀᴄᴋ •", callback_data="help"),
                ]
            ]),
        )

    elif data == "meta":
        await _answer(query)
        await _edit_or_replace(
            query,
            Txt.SEND_METADATA,
            InlineKeyboardMarkup([[
                InlineKeyboardButton("• ᴄʟᴏsᴇ", callback_data="close"),
                InlineKeyboardButton("ʙᴀᴄᴋ •", callback_data="help"),
            ]]),
        )

    elif data == "donate":
        await _answer(query)
        await _edit_or_replace(
            query,
            Txt.DONATE_TXT,
            InlineKeyboardMarkup([[
                InlineKeyboardButton("• ʙᴀᴄᴋ", callback_data="help"),
                InlineKeyboardButton("ᴏᴡɴᴇʀ •", url="https://t.me/ANIFLIXANIMETAMIL"),
            ]]),
        )

    elif data == "file_names":
        await _answer(query)
        try:
            format_template = await codeflixbots.get_format_template(user_id)
        except Exception:
            logger.exception("Could not read format for user %s", user_id)
            format_template = None
        text = Txt.FILE_NAME_TXT
        if format_template:
            text += f"\n\n<b>Your current format:</b> <code>{escape(format_template)}</code>"
        await _edit_or_replace(
            query,
            text,
            InlineKeyboardMarkup([[
                InlineKeyboardButton("• ᴄʟᴏsᴇ", callback_data="close"),
                InlineKeyboardButton("ʙᴀᴄᴋ •", callback_data="help"),
            ]]),
        )

    elif data == "thumbnail":
        await _answer(query)
        await _edit_or_replace(
            query,
            Txt.THUMBNAIL_TXT,
            InlineKeyboardMarkup([[
                InlineKeyboardButton("• ᴄʟᴏsᴇ", callback_data="close"),
                InlineKeyboardButton("ʙᴀᴄᴋ •", callback_data="help"),
            ]]),
        )

    elif data == "source":
        await _answer(query)
        await _edit_or_replace(
            query,
            Txt.SOURCE_TXT,
            InlineKeyboardMarkup([[
                InlineKeyboardButton("• ᴄʟᴏsᴇ", callback_data="close"),
                InlineKeyboardButton("ʙᴀᴄᴋ •", callback_data="home"),
            ]]),
        )

    elif data == "about":
        await _answer(query)
        await _edit_or_replace(
            query,
            Txt.ABOUT_TXT,
            InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("• sᴜᴘᴘᴏʀᴛ", url="https://t.me/anime_tamil_index_chat"),
                    InlineKeyboardButton("ᴄᴏᴍᴍᴀɴᴅs •", callback_data="help"),
                ],
                [
                    InlineKeyboardButton("• ᴅᴇᴠᴇʟᴏᴘᴇʀ", url="https://t.me/ANIFLIXANIMETAMIL"),
                    InlineKeyboardButton("ɴᴇᴛᴡᴏʀᴋ •", url="https://t.me/ANIFLIXANIMETAMIL"),
                ],
                [InlineKeyboardButton("• ʙᴀᴄᴋ •", callback_data="home")],
            ]),
        )

    elif data in {"premiumx", "plans"}:
        await _answer(query)
        text = Txt.PREMIUM_TXT if data == "premiumx" else Txt.PREPLANS_TXT
        await _edit_or_replace(
            query,
            text,
            InlineKeyboardMarkup([[
                InlineKeyboardButton("• ʙᴀᴄᴋ", callback_data="help"),
                InlineKeyboardButton("ᴏᴡɴᴇʀ •", url="https://t.me/ANIFLIXANIMETAMIL"),
            ]]),
        )

    elif data in {"close", "close_data"}:
        await _answer(query)
        try:
            if query.message:
                await query.message.delete()
        except Exception:
            logger.debug("Could not delete menu message", exc_info=True)

    else:
        # Other plugin callbacks (such as metadata and setmedia) are handled by their own
        # handlers. Answering here prevents the Telegram client spinner for unknown data.
        await _answer(query)


async def _temporary_photo_command(message: Message, photo: str, caption: str, buttons) -> None:
    try:
        sent = await message.reply_photo(photo=photo, caption=caption, reply_markup=buttons)
    except Exception:
        logger.exception("Temporary command photo failed; sending text fallback")
        sent = await message.reply_text(
            caption,
            reply_markup=buttons,
            disable_web_page_preview=True,
        )

    async def cleanup():
        await asyncio.sleep(300)
        try:
            await sent.delete()
            await message.delete()
        except Exception:
            logger.debug("Auto-delete of temporary command message failed", exc_info=True)

    asyncio.create_task(cleanup())


@Client.on_message(filters.private & filters.command("donate"))
async def donation(client: Client, message: Message):
    buttons = InlineKeyboardMarkup([[
        InlineKeyboardButton("ʙᴀᴄᴋ", callback_data="help"),
        InlineKeyboardButton("ᴏᴡɴᴇʀ", url="https://t.me/ANIFLIXANIMETAMIL"),
    ]])
    await _temporary_photo_command(
        message,
        "https://graph.org/file/1919fe077848bd0783d4c.jpg",
        Txt.DONATE_TXT,
        buttons,
    )


@Client.on_message(filters.private & filters.command("premium"))
async def getpremium(bot: Client, message: Message):
    buttons = InlineKeyboardMarkup([[
        InlineKeyboardButton("ᴏᴡɴᴇʀ", url="https://t.me/ANIFLIXANIMETAMIL"),
        InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close"),
    ]])
    await _temporary_photo_command(
        message,
        "https://graph.org/file/feebef43bbdf76e796b1b.jpg",
        Txt.PREMIUM_TXT,
        buttons,
    )


@Client.on_message(filters.private & filters.command("plan"))
async def premium(bot: Client, message: Message):
    buttons = InlineKeyboardMarkup([[
        InlineKeyboardButton("sᴇɴᴅ ss", url="https://t.me/ANIFLIXANIMETAMIL"),
        InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close"),
    ]])
    await _temporary_photo_command(
        message,
        "https://graph.org/file/8b50e21db819f296661b7.jpg",
        Txt.PREPLANS_TXT,
        buttons,
    )


@Client.on_message(filters.private & filters.command("bought"))
async def bought(client: Client, message: Message):
    replied = message.reply_to_message
    if not replied or not replied.photo:
        return await message.reply_text(
            "Please reply to a payment screenshot with /bought."
        )
    if Config.LOG_CHANNEL is None:
        return await message.reply_text(
            "⚠️ Admin log channel is not configured. Please contact the bot owner."
        )

    try:
        await client.send_photo(
            chat_id=Config.LOG_CHANNEL,
            photo=replied.photo.file_id,
            caption=(
                f"User: {message.from_user.mention}\n"
                f"User ID: {message.from_user.id}\n"
                f"Username: @{message.from_user.username or 'none'}\n"
                f"Name: {message.from_user.first_name or 'none'}"
            ),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Close", callback_data="close_data")
            ]]),
        )
    except Exception:
        logger.exception("Could not forward a purchase screenshot")
        return await message.reply_text("❌ I couldn't forward the screenshot. Please try again later.")

    await message.reply_text("✅ Your screenshot has been sent to the admins.")


@Client.on_message(filters.private & filters.command("help"))
async def help_command(client: Client, message: Message):
    await message.reply_text(
        text=Txt.HELP_TXT.format(mention=client.mention),
        disable_web_page_preview=True,
        reply_markup=help_keyboard(),
    )
