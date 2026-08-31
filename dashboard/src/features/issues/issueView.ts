import type { IssueDTO, IssueStatus, ReportDTO } from "@/types";
import { resolveMediaUrl } from "@/api/config";
import { displayLocationEn, ensureEnglishPlaces } from "@/utils/locationDisplay";

// Display helpers that bridge the real Issue/Report/Task models to the
// admin-console UI. Fields the backend doesn't track (title, ticket number,
// urgency) are derived from real columns rather than stored separately.

export type DisplayStatus = "Open" | "In Progress" | "Resolved";

const STATUS_LABELS: Record<IssueStatus, DisplayStatus> = {
  open: "Open",
  in_progress: "In Progress",
  resolved: "Resolved",
};

export function getDisplayStatus(status: IssueStatus): DisplayStatus {
  return STATUS_LABELS[status];
}

export function isUrgent(severity: string): boolean {
  const normalized = severity.trim().toLowerCase();
  return normalized === "critical" || normalized === "high";
}

export function getTicketNo(id: number): string {
  return `CIV-${String(id).padStart(6, "0")}`;
}

export function getTitle(issue: IssueDTO): string {
  const place = displayLocationEn(issue.district);
  return `${issue.category} reported in ${place}`;
}

function byCreatedAtAsc(reports: ReportDTO[]): ReportDTO[] {
  return [...reports].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
  );
}

export function getPrimaryReport(issue: IssueDTO): ReportDTO | undefined {
  return byCreatedAtAsc(issue.reports)[0];
}

export function getMergedReports(issue: IssueDTO): ReportDTO[] {
  return byCreatedAtAsc(issue.reports).slice(1);
}

export function getDescription(issue: IssueDTO): string {
  const report = getPrimaryReport(issue);
  if (!report) {
    return "No description provided.";
  }
  // Prefer municipal AI summary/description; normalize any leftover Arabic places.
  const raw = report.ai_summary || report.transcribed_text;
  if (!raw) {
    return "No description provided.";
  }
  return ensureEnglishPlaces(raw, report.location_text ?? issue.district);
}

export function getDisplayLocation(issue: IssueDTO): string {
  return displayLocationEn(issue.district);
}

export function getOriginalLocation(issue: IssueDTO): string | null {
  const original = getPrimaryReport(issue)?.location_text?.trim();
  return original || null;
}

export function getPhotoUrl(issue: IssueDTO): string | null {
  const report = getPrimaryReport(issue);
  if (!report) {
    return null;
  }
  return (
    resolveMediaUrl(report.photo_url) ??
    resolveMediaUrl(report.media_urls?.[0] ?? null)
  );
}

export function maskPhone(phoneNumber: string): string {
  return `••• ${phoneNumber.slice(-4)}`;
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export function timeAgo(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 3600) return `${Math.max(0, Math.floor(diff / 60))}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export function getPinColor(issue: IssueDTO): string {
  if (isUrgent(issue.severity)) return "#EF4444";
  if (issue.status === "in_progress") return "#3B82F6";
  if (issue.status === "resolved") return "#10B981";
  return "#9CA3AF";
}

export function getLatestTask(issue: IssueDTO) {
  if (issue.tasks.length === 0) return undefined;
  return [...issue.tasks].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  )[0];
}
