"""Keyword-based issue classification and simple language detection."""

import re
from typing import Optional

from app.services.whatsapp.schemas import SupportedLanguage

# Keyword groups: canonical issue type -> trigger terms (EN + AR)
ISSUE_KEYWORDS: dict[str, list[str]] = {
    "pothole": ["pothole", "hole", "حفرة", "جور"],
    "garbage": ["garbage", "trash", "زبالة", "نفايات"],
    "street_light": ["light", "street light", "streetlight", "ضو", "انارة", "إنارة", "إضاءة"],
    "water_leak": ["water", "leak", "مي", "مياه", "تسريب"],
    "road_damage": ["road", "طريق", "خراب", "ضرر"],
}

ARABIC_SCRIPT_RE = re.compile(r"[\u0600-\u06FF]")

# Common Lebanese Arabizi / mixed cues (Latin script)
LEBANESE_LATIN_CUES = [
    "kifak",
    "kifik",
    "shu",
    "wayn",
    "wen",
    "ma fi",
    "mafi",
    "yalla",
    "habibi",
    "khalas",
    "ahla",
]

CONFIRM_KEYWORDS = {
    "en": ["yes", "y", "confirm", "confirmed", "ok", "okay", "submit", "correct"],
    "ar": ["نعم", "اي", "أي", "ايه", "أيه", "موافق", "تمام", "صح", "اكيد", "أكيد"],
}

REJECT_KEYWORDS = {
    "en": ["no", "n", "cancel", "wrong", "edit", "change"],
    "ar": ["لا", "لأ", "الغاء", "إلغاء", "غلط", "خطأ"],
}

SKIP_PHOTO_KEYWORDS = {
    "en": ["skip", "no photo", "none", "without photo"],
    "ar": ["تخطي", "بدون صورة", "ما في صورة", "مافي صورة"],
}


def detect_language(text: str) -> SupportedLanguage:
    """Detect Arabic vs English from script and common Lebanese cues."""
    normalized = text.strip().lower()
    if not normalized:
        return SupportedLanguage.EN

    if ARABIC_SCRIPT_RE.search(text):
        return SupportedLanguage.AR

    if any(cue in normalized for cue in LEBANESE_LATIN_CUES):
        return SupportedLanguage.AR

    return SupportedLanguage.EN


def classify_issue(text: str) -> Optional[str]:
    """Return canonical issue type if any keyword group matches, else None."""
    normalized = text.strip().lower()
    if not normalized:
        return None

    for issue_type, keywords in ISSUE_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in normalized:
                return issue_type

    return None


def is_confirmation(text: str) -> bool:
    normalized = text.strip().lower()
    return any(kw in normalized for kw in CONFIRM_KEYWORDS["en"] + CONFIRM_KEYWORDS["ar"])


def is_rejection(text: str) -> bool:
    normalized = text.strip().lower()
    return any(kw in normalized for kw in REJECT_KEYWORDS["en"] + REJECT_KEYWORDS["ar"])


def is_skip_photo(text: str) -> bool:
    normalized = text.strip().lower()
    return any(kw in normalized for kw in SKIP_PHOTO_KEYWORDS["en"] + SKIP_PHOTO_KEYWORDS["ar"])


def format_issue_type(issue_type: str, language: SupportedLanguage) -> str:
    """Human-readable issue label for summaries."""
    labels = {
        "pothole": {"en": "Pothole", "ar": "حفرة"},
        "garbage": {"en": "Garbage", "ar": "زبالة / نفايات"},
        "street_light": {"en": "Street light", "ar": "إنارة"},
        "water_leak": {"en": "Water leak", "ar": "تسريب مياه"},
        "road_damage": {"en": "Road damage", "ar": "ضرر في الطريق"},
    }
    lang_key = language.value
    return labels.get(issue_type, {}).get(lang_key, issue_type.replace("_", " ").title())
