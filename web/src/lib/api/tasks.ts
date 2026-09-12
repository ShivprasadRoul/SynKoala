import { apiFetch } from "../apiClient";
import type { Task } from "../types";

export function listTasks(studyId: string) {
  return apiFetch<Task[]>(`/studies/${studyId}/tasks`);
}

export function createTask(
  studyId: string,
  input: {
    instruction: string;
    starting_point?: string | null;
    success_conditions?: object | null;
    constraints?: object | null;
    expected_critical_actions?: string[] | null;
  }
) {
  return apiFetch<Task>(`/studies/${studyId}/tasks`, { body: input });
}

export function updateTask(
  taskId: string,
  input: {
    instruction?: string;
    starting_point?: string | null;
    success_conditions?: object | null;
    constraints?: object | null;
    expected_critical_actions?: string[] | null;
  }
) {
  return apiFetch<Task>(`/tasks/${taskId}`, { method: "PATCH", body: input });
}
