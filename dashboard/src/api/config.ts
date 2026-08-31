export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

/** Backend origin for static media (e.g. /uploads/reports/...). */
export function getApiOrigin(): string {
  const trimmed = API_BASE_URL.replace(/\/+$/, "");
  return trimmed.replace(/\/api\/v1$/, "");
}

/**
 * Turn a DB-stored media path into a browser-loadable URL.
 * Accepts relative paths (/uploads/...), absolute http(s) URLs, or data URIs.
 */
export function resolveMediaUrl(pathOrUrl: string | null | undefined): string | null {
  if (!pathOrUrl?.trim()) {
    return null;
  }

  const normalized = pathOrUrl.trim().replace(/\\/g, "/");
  if (
    normalized.startsWith("http://") ||
    normalized.startsWith("https://") ||
    normalized.startsWith("data:")
  ) {
    return normalized;
  }

  if (normalized.startsWith("/")) {
    return `${getApiOrigin()}${normalized}`;
  }

  return `${getApiOrigin()}/${normalized}`;
}
