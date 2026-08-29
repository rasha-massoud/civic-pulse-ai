"""Report persistence and intake mapping (WhatsApp → PostgreSQL)."""

import logging

from sqlalchemy.orm import Session

from app.models.issue import Issue, IssueStatus
from app.models.report import Report
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


def create_report_from_intake(db: Session, data: WhatsAppReportData) -> Report:
    """Persist a confirmed WhatsApp report as a new Issue + Report.

    Each intake creates a standalone issue for now. Future AI dedup/clustering
    can merge new reports into existing issues instead of always creating new ones.
    """
    category = map_issue_type_to_category(data.issue_type)
    severity = (data.severity or map_issue_type_to_severity(data.issue_type)).title()
    district = (data.location_text or "Beirut").strip()[:150]
    photo_url = data.media_urls[0] if data.media_urls else None

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
        transcribed_text=data.description or None,
        category=category,
        severity=severity,
        latitude=latitude,
        longitude=longitude,
        photo_url=photo_url,
        language=data.language,
        ai_summary=data.ai_summary,
        ai_confidence=data.ai_confidence,
        ai_image_findings=data.ai_image_findings if data.ai_image_findings else None,
        ai_uncertainties=data.ai_uncertainties if data.ai_uncertainties else None,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    logger.info(
        "WhatsApp report persisted | issue_id=%s report_id=%s category=%s district=%s ai_confidence=%.2f",
        issue.id,
        report.id,
        category,
        district,
        data.ai_confidence or 0.0,
    )
    return report


def get_report(db: Session, report_id: int) -> Report | None:
    return db.get(Report, report_id)
