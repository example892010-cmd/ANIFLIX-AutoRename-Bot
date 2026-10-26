import re
from pathlib import Path


def parse_filename(filename: str) -> dict[str, str]:
    """Extract title, season, episode, and quality from a filename."""
    stem = Path(filename).stem

    season = ""
    episode = ""
    quality = ""

    # Examples: S02E05, S2 Ep5, Season 2 Episode 5
    patterns = [
        r"(?i)\bS(\d{1,2})\s*E(?:P)?\s*(\d{1,3})\b",
        r"(?i)\bS(\d{1,2})\s*[-_. ]+EP?\s*(\d{1,3})\b",
        r"(?i)\bSeason\s*(\d{1,2})\s*[,._ -]*Episode\s*(\d{1,3})\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, stem)
        if match:
            season = match.group(1)
            episode = match.group(2)
            stem = stem[:match.start()] + " " + stem[match.end():]
            break

    quality_match = re.search(
        r"(?i)\b(2160p|1440p|1080p|720p|480p|360p|4k|8k)\b",
        stem,
    )

    if quality_match:
        quality = quality_match.group(1).upper()
        stem = stem[:quality_match.start()] + " " + stem[quality_match.end():]

    # Clean up separators and extra spaces.
    title = re.sub(r"[._]+", " ", stem)
    title = re.sub(r"[\[\](){}]", " ", title)
    title = re.sub(r"\s+", " ", title).strip(" -_.")

    return {
        "title": title or Path(filename).stem,
        "season": season,
        "episode": episode,
        "quality": quality,
    }
