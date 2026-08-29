"""Replaceable local media storage for the single-server MVP."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from app.core.config import settings

PUBLIC_MEDIA_PREFIX = "/uploads"
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_MIME_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
_EXTENSION_MIME_TYPES = {extension: mime for mime, extension in _MIME_EXTENSIONS.items()}


@dataclass(frozen=True)
class StoredMedia:
    public_url: str
    path: Path
    mime_type: str
    size: int


def media_root() -> Path:
    """Return the configured absolute upload root, independent of process cwd."""
    configured = Path(settings.LOCAL_MEDIA_DIR)
    return configured.resolve() if configured.is_absolute() else (_BACKEND_ROOT / configured).resolve()


def store_report_image(
    content: bytes,
    mime_type: str,
    *,
    root: Path | None = None,
) -> StoredMedia:
    """Atomically store an already-validated image under a random filename."""
    extension = _MIME_EXTENSIONS.get(mime_type)
    if extension is None:
        raise ValueError("unsupported image MIME type")
    if not content:
        raise ValueError("image content cannot be empty")

    storage_root = (root or media_root()).resolve()
    report_directory = storage_root / "reports"
    report_directory.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid4().hex}{extension}"
    destination = report_directory / filename
    temporary = report_directory / f".{filename}.tmp"
    try:
        temporary.write_bytes(content)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)

    return StoredMedia(
        public_url=f"{PUBLIC_MEDIA_PREFIX}/reports/{filename}",
        path=destination,
        mime_type=mime_type,
        size=len(content),
    )


def load_report_image(
    public_url: str,
    *,
    root: Path | None = None,
) -> StoredMedia:
    """Load a generated local report URL while preventing path traversal."""
    expected_prefix = f"{PUBLIC_MEDIA_PREFIX}/reports/"
    if not public_url.startswith(expected_prefix):
        raise ValueError("unsupported local image reference")

    filename = public_url.removeprefix(expected_prefix)
    if not filename or Path(filename).name != filename:
        raise ValueError("invalid local image reference")

    mime_type = _EXTENSION_MIME_TYPES.get(Path(filename).suffix.lower())
    if mime_type is None:
        raise ValueError("unsupported local image extension")

    storage_root = (root or media_root()).resolve()
    report_directory = (storage_root / "reports").resolve()
    source = (report_directory / filename).resolve()
    if source.parent != report_directory or not source.is_file():
        raise ValueError("local image does not exist")

    content = source.read_bytes()
    return StoredMedia(
        public_url=public_url,
        path=source,
        mime_type=mime_type,
        size=len(content),
    )
