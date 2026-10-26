import os


def load_config():
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    owner_id_text = os.getenv("OWNER_ID", "").strip()

    if not bot_token:
        raise RuntimeError(
            "BOT_TOKEN is missing. Add it to your Render environment variables."
        )

    if not owner_id_text:
        raise RuntimeError(
            "OWNER_ID is missing. Add your numeric Telegram user ID to Render."
        )

    try:
        owner_id = int(owner_id_text)
    except ValueError as exc:
        raise RuntimeError(
            "OWNER_ID must be a numeric Telegram user ID."
        ) from exc

    if owner_id <= 0:
        raise RuntimeError("OWNER_ID must be a positive number.")

    return {
        "bot_token": bot_token,
        "owner_id": owner_id,
        "port": int(os.getenv("PORT", "10000")),
        "data_dir": os.getenv("DATA_DIR", "data"),
    }
