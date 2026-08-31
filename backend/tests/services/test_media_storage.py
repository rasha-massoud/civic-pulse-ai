"""Tests for MVP local report-image storage."""

from pathlib import Path

import pytest

from app.services.media_storage import load_report_image, store_report_image


def test_stores_and_loads_report_image(tmp_path: Path):
    content = b"\xff\xd8\xffimage data"

    stored = store_report_image(content, "image/jpeg", root=tmp_path)
    loaded = load_report_image(stored.public_url, root=tmp_path)

    assert stored.public_url.startswith("/uploads/reports/")
    assert stored.path.read_bytes() == content
    assert loaded.path == stored.path
    assert loaded.mime_type == "image/jpeg"
    assert loaded.size == len(content)


def test_uses_random_filenames_and_rejects_traversal(tmp_path: Path):
    first = store_report_image(b"one", "image/png", root=tmp_path)
    second = store_report_image(b"two", "image/png", root=tmp_path)

    assert first.public_url != second.public_url
    with pytest.raises(ValueError, match="invalid local image reference"):
        load_report_image("/uploads/reports/../secret.jpg", root=tmp_path)
