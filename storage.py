import json
import os
from pathlib import Path
from threading import Lock

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
SETTINGS_PATH = DATA_DIR / "settings.json"
_lock = Lock()

DEFAULT_SETTINGS = {
    "format": "{title}",
    "thumbnail": "",
    "metadata": "",
}


def load_settings():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with _lock:
        if not SETTINGS_PATH.exists():
            return DEFAULT_SETTINGS.copy()

        try:
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return DEFAULT_SETTINGS.copy()

            settings = DEFAULT_SETTINGS.copy()
            for key in settings:
                if key in data and isinstance(data[key], str):
                    settings[key] = data[key]
            return settings

        except (OSError, json.JSONDecodeError):
            return DEFAULT_SETTINGS.copy()


def save_settings(settings):
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    clean_settings = DEFAULT_SETTINGS.copy()
    for key in clean_settings:
        value = settings.get(key, clean_settings[key])
        if isinstance(value, str):
            clean_settings[key] = value

    temporary_path = SETTINGS_PATH.with_suffix(".tmp")

    with _lock:
        temporary_path.write_text(
            json.dumps(clean_settings, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary_path.replace(SETTINGS_PATH)
