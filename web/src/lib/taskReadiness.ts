import type { Task } from "./types";

// Mirrors app/agents/graphs/simulation_graph.py:has_recognized_success_condition
// exactly — only these three keys are given evaluation semantics by the
// Simulation Engine. Kept in one place so the task builder's own success-
// condition UI and any readiness check (e.g. "can this study be published")
// can't quietly drift out of sync with each other or with the backend.
const RECOGNIZED_SUCCESS_KEYS = ["screen_key", "element_key", "semantic_role"] as const;

export function hasRecognizedSuccessCondition(
  successConditions: Record<string, unknown> | null | undefined
): boolean {
  if (!successConditions) return false;
  return RECOGNIZED_SUCCESS_KEYS.some((key) => key in successConditions);
}

// A task with neither a recognized success condition nor critical actions can
// never reach task_progress 1.0 (update_state caps exploration-only progress
// at 0.9) — every participant is guaranteed to abandon. Same predicate
// app/usecases/simulations.py:task_has_finish_line enforces server-side.
export function taskHasFinishLine(task: Task): boolean {
  return (
    hasRecognizedSuccessCondition(task.success_conditions) ||
    Boolean(task.expected_critical_actions && task.expected_critical_actions.length > 0)
  );
}
