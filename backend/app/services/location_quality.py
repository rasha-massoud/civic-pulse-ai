"""Validate whether a textual location is meaningful enough for intake.

Regex here only rejects obvious empty/generic fragments. Semantic extraction
remains the multimodal model's job.
"""

from __future__ import annotations

import re

# Standalone generics that must not satisfy the location requirement alone.
_GENERIC_LOCATION_TOKENS: frozenset[str] = frozenset(
    {
        "طريق",
        "الطريق",
        "طريقة",
        "شارع",
        "الشارع",
        "ساحة",
        "حي",
        "منطقة",
        "هنا",
        "هناك",
        "قرب",
        "جنب",
        "عند",
        "road",
        "street",
        "st",
        "st.",
        "rd",
        "rd.",
        "avenue",
        "ave",
        "ave.",
        "near",
        "here",
        "there",
        "location",
        "area",
        "place",
        "beirut",
        "بيروت",
    }
)

_ARABIC_LETTER = re.compile(r"[\u0600-\u06FF]")
_LATIN_WORD = re.compile(r"[A-Za-z]{2,}")


def is_meaningful_location(text: str | None) -> bool:
    """True when location_text has identifying information beyond a generic cue."""
    cleaned = (text or "").strip()
    if not cleaned:
        return False

    stripped = normalize_location_candidate(cleaned)
    if not stripped:
        return False

    lowered = stripped.casefold()
    if lowered in _GENERIC_LOCATION_TOKENS or stripped in _GENERIC_LOCATION_TOKENS:
        return False

    # Single generic token even with punctuation.
    tokens = re.split(r"[\s,./\-،]+", stripped)
    tokens = [t for t in tokens if t]
    if len(tokens) == 1 and tokens[0].casefold() in _GENERIC_LOCATION_TOKENS:
        return False
    if len(tokens) == 1 and tokens[0] in _GENERIC_LOCATION_TOKENS:
        return False

    # Require either multiple tokens or one token with enough substance
    # (e.g. "الحمرا", "AUB", "Verdun", "سوديكو").
    if len(tokens) >= 2:
        # "near road" / "على طريق" still generic.
        if all(t.casefold() in _GENERIC_LOCATION_TOKENS or t in _GENERIC_LOCATION_TOKENS for t in tokens):
            return False
        return True

    only = tokens[0]
    if only.casefold() in _GENERIC_LOCATION_TOKENS or only in _GENERIC_LOCATION_TOKENS:
        return False
    # Single landmark / neighborhood name: ≥3 Arabic or Latin letters.
    arabic_chars = len(_ARABIC_LETTER.findall(only))
    if arabic_chars >= 3:
        return True
    if _LATIN_WORD.fullmatch(only) and len(only) >= 3:
        return True
    return False


def normalize_location_candidate(text: str | None) -> str:
    """Strip speech prepositions/clitics for validation — does not geocode or rename."""
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    stripped = re.sub(
        r"^(?:على|في|جنب|قرب|عند|near|at|on|in|by)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip(" .،,-")
    # Proclitic ب without space: بسوديكو → سوديكو (validation only).
    stripped = re.sub(r"^ب(?=[\u0600-\u06FFA-Za-z])", "", stripped)
    return stripped.strip(" .،,-")


def is_usable_citizen_summary(text: str | None) -> bool:
    """False for empty or model 'insufficient evidence' filler copy."""
    cleaned = (text or "").strip()
    if len(cleaned) < 8:
        return False
    lowered = cleaned.casefold()
    if "not enough information" in lowered or "insufficient information" in lowered:
        return False
    if "not enough" in lowered and "information" in lowered:
        return False
    if "لا يوجد" in cleaned and "معلومات" in cleaned:
        return False
    if "معلومات كافية" in cleaned:
        return False
    return True
