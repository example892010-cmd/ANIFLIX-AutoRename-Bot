import os
from pathlib import Path
from telegram import Bot

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
THUMBNAIL_PATH = DATA_DIR / "thumbnail.jpg"


async def save_thumbnail_from_telegram(
    bot: Bot,
    file_id: str,
) -> str:
    """Download and save a thumbnail image locally."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    telegram_file = await bot.get_file(file_id)
    await telegram_file.download_to_drive(custom_path=str(THUMBNAIL_PATH))

    return str(THUMBNAIL_PATH)


def get_thumbnail_path() -> str | None:
    """Return the thumbnail path if the saved file exists."""
    if THUMBNAIL_PATH.exists() and THUMBNAIL_PATH.is_file():
        return str(THUMBNAIL_PATH)
    return None


def delete_thumbnail() -> bool:
    """Delete the saved thumbnail, if present."""
    if not THUMBNAIL_PATH.exists():
        return False

    try:
        THUMBNAIL_PATH.unlink()
        return True
    except OSError:
        return False
