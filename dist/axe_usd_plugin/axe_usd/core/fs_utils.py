from pathlib import Path


def ensure_directory(path: Path) -> Path:
    """Create the directory path if it does not exist.

    Args:
        path: Directory path to create.

    Returns:
        Path: The ensured directory path.
    """
    path.mkdir(parents=True, exist_ok=True)
    return path
