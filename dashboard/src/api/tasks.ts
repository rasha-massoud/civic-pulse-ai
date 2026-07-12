import { apiClient } from "./client";
import type { TaskDTO } from "@/types";

export function createTask(issueId: number, assignedTo: string): Promise<TaskDTO> {
  return apiClient.post<TaskDTO>("/tasks", { issue_id: issueId, assigned_to: assignedTo });
}

export function updateTaskStatus(taskId: number, status: string): Promise<TaskDTO> {
  return apiClient.patch<TaskDTO>(`/tasks/${taskId}`, { status });
}
