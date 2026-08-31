/**
 * English dashboard labels for citizen location phrases.
 * Presentation only — does not invent precision or geocode.
 */

const PLACE_MAP: [string, string][] = [
  ["الجامعة الأميركية", "American University of Beirut"],
  ["الجامعة الأمريكية", "American University of Beirut"],
  ["الطريق البحري", "Coastal Road"],
  ["طريق البحري", "Coastal Road"],
  ["الأشرفية", "Achrafieh"],
  ["اشرفية", "Achrafieh"],
  ["مار مخايل", "Mar Mikhael"],
  ["الحمرا", "Hamra"],
  ["حمرا", "Hamra"],
  ["فردان", "Verdun"],
  ["الروشة", "Raouche"],
  ["روشة", "Raouche"],
  ["الصنائع", "Sanayeh"],
  ["الجميزة", "Gemmayzeh"],
  ["الجمّيزة", "Gemmayzeh"],
  ["ببيروت", "Beirut"],
  ["بيروت", "Beirut"],
].sort((a, b) => b[0].length - a[0].length);

const ARABIC_SCRIPT = /[\u0600-\u06FF]/;

function translateKnownPlaces(text: string): string {
  let result = text;
  for (const [arabic, english] of PLACE_MAP) {
    if (result.includes(arabic)) {
      result = result.split(arabic).join(english);
    }
  }
  return result;
}

/** English display form of a citizen location for the municipality UI. */
export function displayLocationEn(raw: string | null | undefined): string {
  const original = (raw ?? "").trim();
  if (!original) return "Beirut";
  if (!ARABIC_SCRIPT.test(original)) return original;

  let text = original.replace(/^(?:على|في|ب|جنب|قرب|عند)\s+/, "").trim();

  const fullyTranslated = translateKnownPlaces(text).replace(/[،,]+$/g, "").trim();
  if (fullyTranslated && !ARABIC_SCRIPT.test(fullyTranslated)) {
    return fullyTranslated;
  }

  const streetMatch = text.match(/^(?:ال)?(طريق|شارع)\s+(.+)$/);
  if (streetMatch) {
    const rest = translateKnownPlaces(streetMatch[2]).trim().replace(/[،,]+$/g, "");
    if (rest) {
      if (/(street|road|square|avenue)$/i.test(rest)) return rest;
      return `${rest} Street`;
    }
  }

  return translateKnownPlaces(text).trim() || original;
}

/** Replace known Arabic place tokens inside municipal English copy. */
export function ensureEnglishPlaces(
  text: string | null | undefined,
  originalLocation?: string | null,
): string {
  if (!text) return "";
  let result = text;
  const raw = (originalLocation ?? "").trim();
  if (raw && result.includes(raw)) {
    result = result.split(raw).join(displayLocationEn(raw));
  }
  result = translateKnownPlaces(result);
  result = result.replace(/طريق\s+([\u0600-\u06FF]+)/g, (_m, name: string) =>
    displayLocationEn(`طريق ${name}`),
  );
  result = result.replace(/شارع\s+([\u0600-\u06FF]+)/g, (_m, name: string) =>
    displayLocationEn(`شارع ${name}`),
  );
  return result;
}
