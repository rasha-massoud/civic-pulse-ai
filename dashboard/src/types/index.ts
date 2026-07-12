// Wire types mirroring the FastAPI/SQLAlchemy models in backend/app/models.
// Field names are kept snake_case to match the API response shape 1:1.

export type IssueStatus = "open" | "in_progress" | "resolved";

export interface ReportDTO {
  id: number;
  issue_id: number | null;
  phone_number: string;
  transcribed_text: string | null;
  category: string;
  severity: string;
  latitude: number;
  longitude: number;
  photo_url: string | null;
  voice_note_url: string | null;
  language: string;
  created_at: string;
}

export interface TaskDTO {
  id: number;
  issue_id: number;
  assigned_to: string;
  status: string;
  created_at: string;
}

export interface IssueDTO {
  id: number;
  category: string;
  severity: string;
  status: IssueStatus;
  report_count: number;
  district: string;
  latitude: number;
  longitude: number;
  created_at: string;
  updated_at: string;
  reports: ReportDTO[];
  tasks: TaskDTO[];
}
