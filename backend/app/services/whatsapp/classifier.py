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


def _keyword_matches(haystack: str, keyword: str) -> bool:
    """Match keywords without treating طريق as a hit inside طريقة."""
    needle = keyword.lower()
    if not needle:
        return False
    if ARABIC_SCRIPT_RE.search(keyword):
        # Arabic: require non-letter boundaries so substrings do not false-positive.
        pattern = rf"(?<![\u0600-\u06FF]){re.escape(keyword)}(?![\u0600-\u06FF])"
        return re.search(pattern, haystack) is not None
    if " " in needle:
        return needle in haystack
    return re.search(rf"\b{re.escape(needle)}\b", haystack) is not None


def classify_issue(text: str) -> Optional[str]:
    """Return canonical issue type if any keyword group matches, else None.

    Keyword hits are provisional only — multimodal joint evidence is authoritative
    once analysis runs.
    """
    normalized = text.strip().lower()
    if not normalized:
        return None

    for issue_type, keywords in ISSUE_KEYWORDS.items():
        for keyword in keywords:
            if _keyword_matches(normalized if not ARABIC_SCRIPT_RE.search(keyword) else text, keyword):
                return issue_type

    return None


def is_confirmation(text: str) -> bool:
    """True for short confirm replies — not substrings inside report narratives."""
    cleaned = (text or "").strip()
    if not cleaned:
        return False
    tokens = [t for t in re.split(r"[\s,!.?؟،*_]+", cleaned.lower()) if t]
    # Confirmations are typically 1–3 tokens ("yes", "نعم", "ok submit").
    if len(tokens) > 4 or len(cleaned) > 40:
        return False
    keywords = CONFIRM_KEYWORDS["en"] + CONFIRM_KEYWORDS["ar"]
    if cleaned.lower() in keywords or cleaned in keywords:
        return True
    return any(tok in keywords for tok in tokens)


def is_rejection(text: str) -> bool:
    """True for short cancel replies — not 'لا' inside words like 'سلام'."""
    cleaned = (text or "").strip()
    if not cleaned:
        return False
    tokens = [t for t in re.split(r"[\s,!.?؟،*_]+", cleaned.lower()) if t]
    if len(tokens) > 4 or len(cleaned) > 40:
        return False
    keywords = REJECT_KEYWORDS["en"] + REJECT_KEYWORDS["ar"]
    if cleaned.lower() in keywords or cleaned in keywords:
        return True
    return any(tok in keywords for tok in tokens)


def is_skip_photo(text: str) -> bool:
    normalized = text.strip().lower()
    return any(kw in normalized for kw in SKIP_PHOTO_KEYWORDS["en"] + SKIP_PHOTO_KEYWORDS["ar"])


def format_issue_type(issue_type: str, language: SupportedLanguage) -> str:
    """Short normalized category label for citizen-facing WhatsApp confirmation."""
    labels = {
        "pothole": {"en": "Pothole", "ar": "حفرة في الطريق"},
        "garbage": {"en": "Garbage accumulation", "ar": "تراكم نفايات"},
        "street_light": {"en": "Street light outage", "ar": "عطل في إنارة الشارع"},
        "water_leak": {"en": "Water leak", "ar": "تسرب مياه"},
        "road_damage": {"en": "Road damage", "ar": "ضرر في الطريق"},
        "other": {"en": "Other issue", "ar": "مشكلة أخرى"},
    }
    lang_key = language.value
    return labels.get(issue_type, {}).get(lang_key, issue_type.replace("_", " ").title())
