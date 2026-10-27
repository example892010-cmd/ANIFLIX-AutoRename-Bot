"""Pure filename parsing and formatting helpers (no Telegram dependencies)."""

import re
from pathlib import Path

_SEASON_EPISODE_PATTERNS = (
    re.compile(
        r"(?i)\bS(?:eason)?[ ._-]*(\d{1,2})[ ._-]*E(?:P|pisode)?[ ._-]*(\d{1,3})\b"
    ),
    re.compile(r"(?i)\bSeason[ ._-]*(\d{1,2})[ ._-]*Episode[ ._-]*(\d{1,3})\b"),
    re.compile(r"(?i)\b(?:Episode|EP|E)[ ._-]*(\d{1,3})\b"),
)
_QUALITY_PATTERNS = (
    re.compile(r"(?i)\b(2160p|1440p|1080p|720p|480p|360p|240p)\b"),
    re.compile(r"(?i)\b(4k|8k|2k)\b"),
    re.compile(r"(?i)\b(HDRip|HDTV|WEB-DL|WEBRip|BluRay|BRRip)\b"),
    re.compile(r"(?i)\b(4kX264|4kX265|X264|X265|H264|H265|HEVC|AV1)\b"),
)
_PLACEHOLDER_PATTERN = re.compile(r"\{\s*(title|season|episode|quality)\s*\}", re.IGNORECASE)
_INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_WHITESPACE = re.compile(r"\s+")


def source_basename(filename: str | None, fallback: str = "file") -> str:
    """Return a safe basename from a client-supplied filename."""
    raw = str(filename or fallback).replace("\\", "/")
    basename = raw.rsplit("/", 1)[-1].strip()
    return basename or fallback


def extract_season_episode(filename: str) -> tuple[str | None, str | None]:
    """Extract season and episode without treating arbitrary title numbers as episodes."""
    name = source_basename(filename)
    for pattern in _SEASON_EPISODE_PATTERNS:
        match = pattern.search(name)
        if not match:
            continue
        if len(match.groups()) == 2:
            return match.group(1), match.group(2)
        return None, match.group(1)
    return None, None


def extract_quality(filename: str) -> str:
    """Extract common video quality/codec labels from a filename."""
    name = source_basename(filename)
    for pattern in _QUALITY_PATTERNS:
        match = pattern.search(name)
        if match:
            return match.group(1)
    return "Unknown"


def extract_title(filename: str) -> str:
    """Build a useful title by removing recognizable release metadata."""
    stem = Path(source_basename(filename)).stem
    for pattern in _SEASON_EPISODE_PATTERNS:
        stem = pattern.sub(" ", stem)
    for pattern in _QUALITY_PATTERNS:
        stem = pattern.sub(" ", stem)
    stem = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", stem)
    stem = re.sub(r"(?i)\b(dual audio|multi audio|tamil audio|eng sub|japanese audio)\b", " ", stem)
    stem = re.sub(r"[._]+", " ", stem)
    stem = _WHITESPACE.sub(" ", stem).strip(" .-_[]()")
    return stem or Path(source_basename(filename)).stem or "file"


def sanitize_filename(filename: str, max_length: int = 240) -> str:
    """Remove path/control/reserved characters and keep a single filename."""
    filename = str(filename or "renamed_file").replace("\\", "_").replace("/", "_")
    filename = _INVALID_FILENAME_CHARS.sub("_", filename)
    filename = _WHITESPACE.sub(" ", filename).strip(" .")
    if not filename or filename in {".", ".."}:
        filename = "renamed_file"

    path = Path(filename)
    suffix = path.suffix
    stem = path.stem
    # Keep room for the suffix while avoiding Telegram/OS path-length problems.
    if len(filename) > max_length:
        available = max(1, max_length - len(suffix))
        filename = stem[:available] + suffix
    return filename


def render_filename(original_filename: str, template: str) -> str:
    """Resolve supported placeholders and append the original extension once.

    Supported placeholders: {title}, {season}, {episode}, {quality}.
    Legacy tokens such as Sseason/Eepisode and standalone quality are supported.
    """
    original = source_basename(original_filename)
    original_path = Path(original)
    extension = original_path.suffix
    values = {
        "title": extract_title(original),
        "season": None,
        "episode": None,
        "quality": extract_quality(original),
    }
    values["season"], values["episode"] = extract_season_episode(original)
    values["season"] = values["season"] or "XX"
    values["episode"] = values["episode"] or "XX"

    text = str(template or "{title} [S{season}E{episode}] [{quality}]").strip()

    # Translate the original README's legacy example format before resolving braces.
    text = re.sub(r"(?i)\bSseason\b", "S{season}", text)
    text = re.sub(r"(?i)\bEepisode\b", "E{episode}", text)
    # Replace legacy word-form quality labels, but not the word inside {quality}.
    text = re.sub(r"(?i)(?<!\{)\bquality\b(?!\})", "{quality}", text)

    # Resolve placeholders case-insensitively. Unknown placeholders are kept temporarily
    # so they can be removed in the cleanup step rather than leaked into filenames.
    text = _PLACEHOLDER_PATTERN.sub(
        lambda match: str(values[match.group(1).lower()]), text
    )
    text = re.sub(r"\{[^{}]*\}", "", text)
    text = _WHITESPACE.sub(" ", text).strip(" .")
    text = re.sub(r"\[\s*\]|\(\s*\)", "", text)
    text = _WHITESPACE.sub(" ", text).strip(" .")

    # If the user included the same extension in the template, don't duplicate it.
    if extension and not text.lower().endswith(extension.lower()):
        text += extension
    elif not extension and not Path(text).suffix:
        # Keep extensionless names extensionless instead of inventing .mp3/.mp4.
        pass

    return sanitize_filename(text)


def metadata_enabled(value) -> bool:
    """Accept legacy DB values (True, 'On', 'Off') consistently."""
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "enabled"}


def format_caption(template: str | None, filename: str, filesize: int, duration: int | None) -> str:
    """Fill the caption placeholders documented by the bot."""
    if not template:
        return filename

    size = _human_bytes(filesize)
    duration_text = _duration_text(duration)
    values = {
        "filename": filename,
        "filesize": size,
        "duration": duration_text,
    }
    result = str(template)
    for key, value in values.items():
        result = re.sub(
            r"\{" + re.escape(key) + r"\}",
            lambda _match, replacement=value: replacement,
            result,
            flags=re.IGNORECASE,
        )
    return result


def _human_bytes(value: int) -> str:
    size = float(max(0, value or 0))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.2f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.2f} TB"


def _duration_text(seconds: int | None) -> str:
    if seconds is None:
        return "Unknown"
    try:
        total = max(0, int(seconds))
    except (TypeError, ValueError):
        return "Unknown"
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"
