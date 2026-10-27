"""MongoDB-backed per-user settings for the auto-rename bot."""

import logging
from datetime import date
from typing import Any

import motor.motor_asyncio

from config import Config
from .utils import send_log

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, uri: str, database_name: str):
        uri = (uri or "").strip()
        if not uri.startswith(("mongodb://", "mongodb+srv://")):
            raise ValueError(
                "DB_URL is missing or invalid. Set it to a MongoDB connection URI "
                "starting with mongodb:// or mongodb+srv:// in Render Environment."
            )
        if not database_name:
            raise ValueError("DB_NAME cannot be empty.")

        # Motor connects lazily. Don't call async server_info() from __init__.
        self._client = motor.motor_asyncio.AsyncIOMotorClient(
            uri,
            serverSelectionTimeoutMS=8000,
            connectTimeoutMS=8000,
        )
        self.codeflixbots = self._client[database_name]
        self.col = self.codeflixbots.user

    @staticmethod
    def new_user(user_id: int) -> dict[str, Any]:
        return {
            "_id": int(user_id),
            "join_date": date.today().isoformat(),
            "file_id": None,
            "caption": None,
            "metadata": "On",
            "metadata_code": "Telegram : @ANIFLIXANIMETAMIL",
            "format_template": None,
            "media_type": None,
            "title": "Encoded by ANIFLIX NETWORK TAMIL",
            "author": "ANIFLIX NETWORK TAMIL",
            "artist": "ANIFLIX NETWORK TAMIL",
            "audio": "By ANIFLIX NETWORK TAMIL",
            "subtitle": "By ANIFLIX NETWORK TAMIL",
            "video": "Encoded By ANIFLIX NETWORK TAMIL",
            "ban_status": {
                "is_banned": False,
                "ban_duration": 0,
                "banned_on": date.max.isoformat(),
                "ban_reason": "",
            },
        }

    async def _ensure_user(self, user_id: int) -> None:
        user_id = int(user_id)
        defaults = self.new_user(user_id)
        defaults.pop("_id", None)
        await self.col.update_one(
            {"_id": user_id},
            {"$setOnInsert": {"_id": user_id, **defaults}},
            upsert=True,
        )

    async def _get_value(self, user_id: int, key: str, default: Any = None) -> Any:
        await self._ensure_user(user_id)
        document = await self.col.find_one({"_id": int(user_id)}, {key: 1})
        if not document:
            return default
        value = document.get(key, default)
        return default if value is None else value

    async def _set_value(self, user_id: int, key: str, value: Any) -> None:
        await self._ensure_user(user_id)
        await self.col.update_one(
            {"_id": int(user_id)}, {"$set": {key: value}}, upsert=True
        )

    async def add_user(self, bot, message) -> None:
        user = getattr(message, "from_user", None)
        if user is None:
            return

        result = await self.col.update_one(
            {"_id": int(user.id)},
            {"$setOnInsert": self.new_user(user.id)},
            upsert=True,
        )
        if result.upserted_id is not None:
            try:
                await send_log(bot, user)
            except Exception:
                logger.exception("Could not send new-user log for %s", user.id)

    async def is_user_exist(self, user_id: int) -> bool:
        document = await self.col.find_one({"_id": int(user_id)}, {"_id": 1})
        return document is not None

    async def total_users_count(self) -> int:
        return await self.col.count_documents({})

    async def get_all_users(self):
        # Return Motor's async cursor for the broadcast command.
        return self.col.find({})

    async def delete_user(self, user_id: int) -> None:
        await self.col.delete_one({"_id": int(user_id)})

    async def set_thumbnail(self, user_id: int, file_id: str | None) -> None:
        await self._set_value(user_id, "file_id", file_id)

    async def get_thumbnail(self, user_id: int):
        return await self._get_value(user_id, "file_id")

    async def set_caption(self, user_id: int, caption: str | None) -> None:
        await self._set_value(user_id, "caption", caption)

    async def get_caption(self, user_id: int):
        return await self._get_value(user_id, "caption")

    async def set_format_template(self, user_id: int, format_template: str | None) -> None:
        await self._set_value(user_id, "format_template", format_template)

    async def get_format_template(self, user_id: int):
        return await self._get_value(user_id, "format_template")

    async def set_media_preference(self, user_id: int, media_type: str | None) -> None:
        await self._set_value(user_id, "media_type", media_type)

    async def get_media_preference(self, user_id: int):
        return await self._get_value(user_id, "media_type")

    async def get_metadata(self, user_id: int):
        return await self._get_value(user_id, "metadata", "On")

    async def set_metadata(self, user_id: int, metadata: str | bool) -> None:
        if isinstance(metadata, bool):
            metadata = "On" if metadata else "Off"
        await self._set_value(user_id, "metadata", str(metadata))

    async def get_title(self, user_id: int):
        return await self._get_value(user_id, "title", "Encoded by ANIFLIX NETWORK TAMIL")

    async def set_title(self, user_id: int, title: str) -> None:
        await self._set_value(user_id, "title", title)

    async def get_author(self, user_id: int):
        return await self._get_value(user_id, "author", "ANIFLIX NETWORK TAMIL")

    async def set_author(self, user_id: int, author: str) -> None:
        await self._set_value(user_id, "author", author)

    async def get_artist(self, user_id: int):
        return await self._get_value(user_id, "artist", "ANIFLIX NETWORK TAMIL")

    async def set_artist(self, user_id: int, artist: str) -> None:
        await self._set_value(user_id, "artist", artist)

    async def get_audio(self, user_id: int):
        return await self._get_value(user_id, "audio", "By ANIFLIX NETWORK TAMIL")

    async def set_audio(self, user_id: int, audio: str) -> None:
        await self._set_value(user_id, "audio", audio)

    async def get_subtitle(self, user_id: int):
        return await self._get_value(user_id, "subtitle", "By ANIFLIX NETWORK TAMIL")

    async def set_subtitle(self, user_id: int, subtitle: str) -> None:
        await self._set_value(user_id, "subtitle", subtitle)

    async def get_video(self, user_id: int):
        return await self._get_value(user_id, "video", "Encoded By ANIFLIX NETWORK TAMIL")

    async def set_video(self, user_id: int, video: str) -> None:
        await self._set_value(user_id, "video", video)

    async def close(self) -> None:
        self._client.close()


codeflixbots = Database(Config.DB_URL, Config.DB_NAME)
