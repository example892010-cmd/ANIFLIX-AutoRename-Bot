import os
import tempfile
from pathlib import Path
from contextlib import contextmanager


@contextmanager
def temporary_file(suffix: str = ""):
    """Create a temporary file and remove it automatically afterward."""
    file_path = None

    try:
        with tempfile.NamedTemporaryFile(
            prefix="aniflix_",
            suffix=suffix,
            delete=False,
        ) as temp_file:
            file_path = Path(temp_file.name)

        yield file_path

    finally:
        if file_path is not None:
            try:
                file_path.unlink(missing_ok=True)
            except OSError:
                pass


def safe_file_size(file_path: str | Path) -> int:
    """Return file size, or zero if the file is unavailable."""
    try:
        return os.path.getsize(file_path)
    except OSError:
        return 0
