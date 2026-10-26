from pathlib import Path
from mutagen import File as MutagenFile


def apply_metadata(file_path: str, metadata_text: str) -> tuple[bool, str]:
    """
    Apply metadata to a supported media file.

    Metadata text format:
    title=My Anime
    artist=ANIFLIX
    comment=Tamil Audio

    Only formats supported by Mutagen can be edited.
    """
    if not metadata_text.strip():
        return True, "No metadata changes requested."

    path = Path(file_path)

    try:
        media = MutagenFile(str(path), easy=True)

        if media is None:
            return False, "This file format does not support metadata editing."

        if media.tags is None:
            try:
                media.add_tags()
            except Exception:
                return False, "Could not create metadata tags for this file."

        for line in metadata_text.splitlines():
            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip().lower()
            value = value.strip()

            if key and value:
                try:
                    media[key] = [value]
                except (KeyError, ValueError):
                    continue

        media.save()
        return True, "Metadata updated successfully."

    except Exception:
        return False, "Metadata could not be updated for this file."
