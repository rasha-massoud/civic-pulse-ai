"""Tests for report persistence and public media URL normalization."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.report import Report
from app.services.reports import create_report_from_intake, normalize_public_media_urls
from app.services.whatsapp.schemas import WhatsAppReportData


def test_normalize_public_media_urls_accepts_uploads_paths():
    urls = normalize_public_media_urls(
        ["/uploads/reports/abc.jpg", r"\uploads\reports\def.png"]
    )
    assert urls == ["/uploads/reports/abc.jpg", "/uploads/reports/def.png"]


def test_normalize_public_media_urls_rejects_meta_and_filesystem_paths():
    urls = normalize_public_media_urls(
        [
            "meta:12345",
            r"C:\Users\user\uploads\photo.jpg",
            "/uploads/reports/valid.webp",
        ]
    )
    assert urls == ["/uploads/reports/valid.webp"]


def test_create_report_from_intake_persists_public_photo_url():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    report = create_report_from_intake(
        db,
        WhatsAppReportData(
            reporter_phone="96170000000",
            issue_type="pothole",
            description="Large pothole on Hamra road",
            location_text="Hamra, Beirut",
            media_urls=["meta:unresolved", "/uploads/reports/abc123.jpg"],
            language="ar",
        ),
    )

    assert report.photo_url == "/uploads/reports/abc123.jpg"
    assert report.media_urls == ["/uploads/reports/abc123.jpg"]

    stored = db.get(Report, report.id)
    assert stored is not None
    assert stored.photo_url == "/uploads/reports/abc123.jpg"
    db.close()


def test_create_report_from_intake_without_photo():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    report = create_report_from_intake(
        db,
        WhatsAppReportData(
            reporter_phone="96170000000",
            issue_type="garbage",
            description="Overflowing bin",
            location_text="Achrafieh",
            media_urls=[],
            language="en",
        ),
    )

    assert report.photo_url is None
    assert report.media_urls is None
    db.close()
