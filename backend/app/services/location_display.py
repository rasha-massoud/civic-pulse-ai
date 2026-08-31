"""Presentation helpers: English dashboard location labels from citizen text.

Does not geocode or invent precision. Original citizen wording must be stored
separately when normalizing for display.
"""

from __future__ import annotations

import re

# Common Beirut / Lebanese place names (Arabic script → English display).
# Longer keys first so multi-word phrases win over shorter tokens.
_PLACE_NAME_MAP: tuple[tuple[str, str], ...] = tuple(
    sorted(
        (
            ("الجامعة الأميركية", "American University of Beirut"),
            ("الجامعة الأمريكية", "American University of Beirut"),
            ("الطريق البحري", "Coastal Road"),
            ("طريق البحري", "Coastal Road"),
            ("الأشرفية", "Achrafieh"),
            ("اشرفية", "Achrafieh"),
            ("مار مخايل", "Mar Mikhael"),
            ("الحمرا", "Hamra"),
            ("حمرا", "Hamra"),
            ("فردان", "Verdun"),
            ("الروشة", "Raouche"),
            ("روشة", "Raouche"),
            ("الصنائع", "Sanayeh"),
            ("الجميزة", "Gemmayzeh"),
            ("الجمّيزة", "Gemmayzeh"),
            ("الداونية", "Dawra"),
            ("الدورة", "Dawra"),
            ("ببيروت", "Beirut"),
            ("بيروت", "Beirut"),
            ("عرمون", "Aaramoun"),
            ("جونيه", "Jounieh"),
            ("صيدا", "Saida"),
            ("طرابلس", "Tripoli"),
        ),
        key=lambda pair: len(pair[0]),
        reverse=True,
    )
)

_STREET_PREFIXES = (
    ("طريق", "Street"),
    ("شارع", "Street"),
    ("ساحة", "Square"),
    ("حي", "Neighborhood"),
)


def _translate_known_places(text: str) -> str:
    result = text
    for arabic, english in _PLACE_NAME_MAP:
        if arabic in result:
            result = result.replace(arabic, english)
    return result


def display_location_en(raw: str | None) -> str:
    """Return an English dashboard label for a citizen location phrase.

    Preserves meaning without inventing a more precise address. Falls back to
    the original text when no useful normalization is possible.
    """
    original = (raw or "").strip()
    if not original:
        return "Beirut"

    # Already mostly Latin — keep as-is (minor cleanup).
    if not re.search(r"[\u0600-\u06FF]", original):
        return original[:150]

    text = original
    # Strip common Arabic prepositions used in speech.
    text = re.sub(r"^(?:على|في|ب|جنب|قرب|عند)\s+", "", text).strip()

    # Translate multi-word landmarks/roads on the full phrase first.
    fully_translated = _translate_known_places(text).strip(" ،,")
    if fully_translated and not re.search(r"[\u0600-\u06FF]", fully_translated):
        return fully_translated[:150]

    # "طريق الحمرا" / "شارع فردان" → "Hamra Street" / "Verdun Street"
    for prefix_ar, suffix_en in _STREET_PREFIXES:
        pattern = rf"^(?:ال)?{re.escape(prefix_ar)}\s+(.+)$"
        match = re.match(pattern, text)
        if match:
            rest = _translate_known_places(match.group(1).strip())
            rest = rest.strip(" ،,")
            if rest:
                if rest.lower().endswith(("street", "road", "square", "avenue")):
                    return rest[:150]
                return f"{rest} {suffix_en}"[:150]

    translated = _translate_known_places(text).strip()
    return (translated or original)[:150]


def ensure_english_places(text: str | None, *, original_location: str | None = None) -> str | None:
    """Replace known Arabic place phrases in municipal English text for display.

    Does not invent content — only substitutes known tokens / the original
    location phrase with its English display form.
    """
    if text is None:
        return None
    result = text
    raw_loc = (original_location or "").strip()
    if raw_loc and raw_loc in result:
        result = result.replace(raw_loc, display_location_en(raw_loc))
    result = _translate_known_places(result)
    # Common street patterns left inside sentences.
    result = re.sub(
        r"طريق\s+([\u0600-\u06FF]+)",
        lambda m: f"{display_location_en('طريق ' + m.group(1))}",
        result,
    )
    result = re.sub(
        r"شارع\s+([\u0600-\u06FF]+)",
        lambda m: f"{display_location_en('شارع ' + m.group(1))}",
        result,
    )
    return result
