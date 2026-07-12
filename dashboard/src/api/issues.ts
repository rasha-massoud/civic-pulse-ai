import { apiClient } from "./client";
import type { IssueDTO, IssueStatus } from "@/types";

export function listIssues(): Promise<IssueDTO[]> {
  return apiClient.get<IssueDTO[]>("/issues");
}

export function getIssue(issueId: number): Promise<IssueDTO> {
  return apiClient.get<IssueDTO>(`/issues/${issueId}`);
}

export function updateIssueStatus(issueId: number, status: IssueStatus): Promise<IssueDTO> {
  return apiClient.patch<IssueDTO>(`/issues/${issueId}`, { status });
}
