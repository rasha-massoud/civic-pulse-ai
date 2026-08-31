"""Report persistence and intake mapping (WhatsApp → PostgreSQL)."""

import logging

from sqlalchemy.orm import Session

from app.models.issue import Issue, IssueStatus
from app.models.report import Report
from app.services.location_display import display_location_en, ensure_english_places
from app.services.media_storage import PUBLIC_MEDIA_PREFIX
from app.services.whatsapp.schemas import WhatsAppReportData

logger = logging.getLogger(__name__)

# Beirut default coordinates until geocoding is implemented (MAPS_API_KEY).
BEIRUT_DEFAULT_LAT = 33.8938
BEIRUT_DEFAULT_LNG = 35.5018

# Map WhatsApp classifier slugs to dashboard category labels.
ISSUE_TYPE_TO_CATEGORY: dict[str, str] = {
    "pothole": "Pothole",
    "garbage": "Garbage Overflow",
    "street_light": "Broken Streetlight",
    "water_leak": "Water Leak",
    "road_damage": "Damaged Sidewalk",
    "other": "Other",
}

ISSUE_TYPE_TO_SEVERITY: dict[str, str] = {
    "water_leak": "High",
    "pothole": "Medium",
    "garbage": "Medium",
    "street_light": "Low",
    "road_damage": "Medium",
    "other": "Medium",
}

_PUBLIC_REPORTS_PREFIX = f"{PUBLIC_MEDIA_PREFIX}/reports/"


def normalize_phone(phone: str) -> str:
    """Normalize a WhatsApp sender phone for database storage.

    Meta Cloud API sends digits (e.g. 96170123456). Ensure a leading '+' for
    consistent storage across intakes.
    """
    cleaned = (phone or "").strip()
    if cleaned.startswith("+"):
        return cleaned
    digits = "".join(ch for ch in cleaned if ch.isdigit())
    return f"+{digits}" if digits else cleaned


def map_issue_type_to_category(issue_type: str) -> str:
    return ISSUE_TYPE_TO_CATEGORY.get(issue_type, "Other")


def map_issue_type_to_severity(issue_type: str) -> str:
    return ISSUE_TYPE_TO_SEVERITY.get(issue_type, "Medium")


def normalize_public_media_urls(urls: list[str] | None) -> list[str]:
    """Keep only browser-servable public paths (never meta: IDs or filesystem paths)."""
    if not urls:
        return []

    normalized: list[str] = []
    for raw in urls:
        ref = (raw or "").strip().replace("\\", "/")
        if not ref:
            continue
        if ref.startswith("meta:"):
            logger.warning(
                "Skipping unresolved Meta media reference at persist time | ref=%s",
                ref[:48],
            )
            continue
        if ref.startswith(_PUBLIC_REPORTS_PREFIX):
            normalized.append(ref)
            continue
        if ref.startswith(("https://", "http://", "data:image/")):
            normalized.append(ref)
            continue
        logger.warning(
            "Skipping invalid media reference at persist time | ref=%s",
            ref[:48],
        )
    return normalized


def create_report_from_intake(db: Session, data: WhatsAppReportData) -> Report:
    """Persist a confirmed WhatsApp report as a new Issue + Report.

    Each intake creates a standalone issue for now. Future AI dedup/clustering
    can merge new reports into existing issues instead of always creating new ones.
    """
    category = map_issue_type_to_category(data.issue_type)
    severity = (data.severity or map_issue_type_to_severity(data.issue_type)).title()
    original_location = (data.location_text or "").strip() or None
    # Dashboard (English) uses a display label; original citizen text is retained
    # on the report row and is never destroyed.
    district = display_location_en(original_location)
    media_urls = normalize_public_media_urls(list(data.media_urls))
    photo_url = media_urls[0] if media_urls else None

    municipal_description = ensure_english_places(
        data.description or None, original_location=original_location
    )
    municipal_summary = ensure_english_places(
        data.ai_summary, original_location=original_location
    )

    # Preserve native citizen coordinates. Text-only locations retain the
    # legacy Beirut fallback until the maps/geocoding service is implemented.
    latitude = data.latitude if data.latitude is not None else BEIRUT_DEFAULT_LAT
    longitude = data.longitude if data.longitude is not None else BEIRUT_DEFAULT_LNG

    issue = Issue(
        category=category,
        severity=severity,
        status=IssueStatus.OPEN,
        report_count=1,
        district=district,
        latitude=latitude,
        longitude=longitude,
    )
    db.add(issue)
    db.flush()

    report = Report(
        issue_id=issue.id,
        phone_number=normalize_phone(data.reporter_phone),
        transcribed_text=municipal_description,
        category=category,
        severity=severity,
        latitude=latitude,
        longitude=longitude,
        photo_url=photo_url,
        media_urls=media_urls or None,
        location_text=original_location,
        language=data.language,
        ai_summary=municipal_summary,
        ai_confidence=data.ai_confidence,
        ai_image_findings=data.ai_image_findings if data.ai_image_findings else None,
        ai_uncertainties=data.ai_uncertainties if data.ai_uncertainties else None,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    logger.info(
        "WhatsApp report persisted | issue_id=%s report_id=%s category=%s district=%s "
        "photo_url=%s media_count=%d ai_confidence=%.2f",
        issue.id,
        report.id,
        category,
        district,
        photo_url or "-",
        len(media_urls),
        data.ai_confidence or 0.0,
    )
    return report


def get_report(db: Session, report_id: int) -> Report | None:
    return db.get(Report, report_id)
