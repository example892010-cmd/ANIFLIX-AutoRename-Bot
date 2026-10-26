import re
from pathlib import Path

ALLOWED_FIELDS = {"title", "season", "episode", "quality", "extension"}


def clean_filename(name: str) -> str:
    """Remove characters that are unsafe in filenames."""
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", name)
    name = name.strip(" .")
    return (name or "renamed_file")[:180]


def build_filename(original_name: str, template: str) -> str:
    """Build a filename without leaving unresolved placeholders."""
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

    def replace_placeholder(match):
        key = match.group(1)
        if key not in ALLOWED_FIELDS:
            return ""
        return values.get(key, "")

    # Replace supported placeholders and remove unsupported ones.
    result = re.sub(r"\{([^{}]+)\}", replace_placeholder, template)
    result = re.sub(r"\s+", " ", result).strip()

    result = clean_filename(result)

    # Preserve the original extension.
    if extension and not result.lower().endswith(extension.lower()):
        result = clean_filename(result)[:180 - len(extension)] + extension

    return result
