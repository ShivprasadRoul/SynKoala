"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useState } from "react";

import { getBenchmark, uploadBenchmark } from "@/lib/api/benchmark";
import { listStimuli } from "@/lib/api/stimulus";
import { createTask, listTasks, updateTask } from "@/lib/api/tasks";
import type { Stimulus, Task } from "@/lib/types";

import { Button } from "@/components/ui/Button";
import { Card, CardDescription, CardTitle } from "@/components/ui/Card";
import { Input, Label, Textarea } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";

// "cart_button, checkout_button" -> ["cart_button", "checkout_button"]; empty
// input -> null (not []), so a task that never set this looks the same as one
// explicitly cleared, matching what the backend treats as "not declared".
function parseCriticalActions(raw: string): string[] | null {
  const actions = raw
    .split(",")
    .map((a) => a.trim())
    .filter(Boolean);
  return actions.length > 0 ? actions : null;
}

// The task's finish line. Only these three keys are given evaluation semantics
// by the Simulation Engine (`has_recognized_success_condition`); a task with
// neither this nor critical actions can never reach task_progress 1.0, so
// `POST /simulations` rejects it rather than run a guaranteed 100% drop-off.
const SUCCESS_KEYS = [
  { value: "screen_key", label: "Reaches screen" },
  { value: "element_key", label: "Interacts with element" },
  { value: "semantic_role", label: "Interacts with role" },
] as const;

type SuccessKey = (typeof SUCCESS_KEYS)[number]["value"];

function parseSuccessConditions(key: SuccessKey, raw: string): Record<string, string> | null {
  const value = raw.trim();
  return value ? { [key]: value } : null;
}

function readSuccessConditions(task: Task): { key: SuccessKey; value: string } {
  for (const { value: key } of SUCCESS_KEYS) {
    const existing = task.success_conditions?.[key];
    if (typeof existing === "string") return { key, value: existing };
  }
  return { key: "screen_key", value: "" };
}

// The Stimulus Engine classifies every analyzed screen's role in the flow
// (`classify_screens`, stored on screens.analysis.flow). Reading the entry and
// success screens back here is what lets the task builder propose a start and
// finish line instead of making the researcher recall screen keys by hand.
function detectedFlowScreens(stimuli: Stimulus[] | undefined): {
  entry: string | null;
  success: string | null;
} {
  let entry: string | null = null;
  let success: string | null = null;
  for (const stimulus of stimuli ?? []) {
    for (const screen of stimulus.screens ?? []) {
      const flow = screen.analysis?.flow as { role?: string } | undefined;
      if (flow?.role === "entry") entry = screen.screen_key;
      if (flow?.role === "success") success = screen.screen_key;
    }
  }
  return { entry, success };
}

function TaskEditForm({ task, onDone }: { task: Task; onDone: () => void }) {
  const queryClient = useQueryClient();
  const [instruction, setInstruction] = useState(task.instruction);
  const [startingPoint, setStartingPoint] = useState(task.starting_point ?? "");
  const [criticalActions, setCriticalActions] = useState(
    (task.expected_critical_actions ?? []).join(", ")
  );
  const existingSuccess = readSuccessConditions(task);
  const [successKey, setSuccessKey] = useState<SuccessKey>(existingSuccess.key);
  const [successValue, setSuccessValue] = useState(existingSuccess.value);

  const editMutation = useMutation({
    mutationFn: () =>
      updateTask(task.id, {
        instruction,
        starting_point: startingPoint || null,
        success_conditions: parseSuccessConditions(successKey, successValue),
        expected_critical_actions: parseCriticalActions(criticalActions),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks", task.study_id] });
      onDone();
    },
  });

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        editMutation.mutate();
      }}
      className="flex flex-col gap-3"
    >
      <Textarea rows={2} value={instruction} onChange={(e) => setInstruction(e.target.value)} />
      <Input
        placeholder="Starting point (optional)"
        value={startingPoint}
        onChange={(e) => setStartingPoint(e.target.value)}
      />
      <div className="flex gap-2">
        <Select
          className="w-auto"
          value={successKey}
          onChange={(e) => setSuccessKey(e.target.value as SuccessKey)}
        >
          {SUCCESS_KEYS.map((key) => (
            <option key={key.value} value={key.value}>
              {key.label}
            </option>
          ))}
        </Select>
        <Input
          placeholder="Task is done when… (e.g. dashboard)"
          value={successValue}
          onChange={(e) => setSuccessValue(e.target.value)}
        />
      </div>
      <Input
        placeholder="Critical actions, comma-separated (e.g. add_to_cart)"
        value={criticalActions}
        onChange={(e) => setCriticalActions(e.target.value)}
      />
      {editMutation.isError && (
        <p className="text-[13px] text-semantic-warn">
          {editMutation.error instanceof Error ? editMutation.error.message : "Failed to save"}
        </p>
      )}
      <div className="flex gap-2">
        <Button type="submit" disabled={editMutation.isPending}>
          {editMutation.isPending ? "Saving…" : "Save"}
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

export default function TaskPage() {
  const { id: studyId } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const { data: tasks, isLoading } = useQuery({
    queryKey: ["tasks", studyId],
    queryFn: () => listTasks(studyId),
  });
  const [editingTaskId, setEditingTaskId] = useState<string | null>(null);

  const [instruction, setInstruction] = useState("");
  const [startingPoint, setStartingPoint] = useState("");
  const [criticalActions, setCriticalActions] = useState("");
  const [successKey, setSuccessKey] = useState<SuccessKey>("screen_key");
  const [successValue, setSuccessValue] = useState("");

  const { data: stimuli } = useQuery({
    queryKey: ["stimuli", studyId],
    queryFn: () => listStimuli(studyId),
  });
  const detected = detectedFlowScreens(stimuli);

  const createMutation = useMutation({
    mutationFn: () =>
      createTask(studyId, {
        instruction,
        starting_point: startingPoint || null,
        success_conditions: parseSuccessConditions(successKey, successValue),
        expected_critical_actions: parseCriticalActions(criticalActions),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks", studyId] });
      setInstruction("");
      setStartingPoint("");
      setCriticalActions("");
      setSuccessValue("");
    },
  });

  // --- Human benchmark (optional, planning/12-web-app.md §5.5): real human
  // task-outcome data for the same task, used to compute how well the
  // synthetic population's completion rate agrees with it (Validation
  // Engine, planning/10). Only `task_outcomes.completion_rate`/`sample_size`
  // get dedicated fields — everything else the backend accepts
  // (interaction_rates/segment_labels/attention_data) is freeform JSON a
  // researcher can paste under "Advanced", not worth a bespoke field per key. ---
  const { data: benchmark } = useQuery({
    queryKey: ["benchmark", studyId],
    queryFn: () => getBenchmark(studyId),
  });
  const [benchmarkSource, setBenchmarkSource] = useState("");
  const [completionRate, setCompletionRate] = useState("");
  const [sampleSize, setSampleSize] = useState("");
  const [extraJson, setExtraJson] = useState("");
  const [benchmarkJsonError, setBenchmarkJsonError] = useState<string | null>(null);

  const benchmarkMutation = useMutation({
    mutationFn: () => {
      let extra: Record<string, unknown> = {};
      if (extraJson.trim()) {
        try {
          extra = JSON.parse(extraJson);
        } catch {
          throw new Error("Advanced JSON must be valid JSON");
        }
      }
      return uploadBenchmark(studyId, {
        source: benchmarkSource || null,
        task_outcomes: {
          ...(completionRate ? { completion_rate: Number(completionRate) } : {}),
          ...(sampleSize ? { sample_size: Number(sampleSize) } : {}),
        },
        interaction_rates: extra.interaction_rates as Record<string, unknown> | undefined,
        segment_labels: extra.segment_labels as Record<string, unknown> | undefined,
        attention_data: extra.attention_data as Record<string, unknown> | undefined,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["benchmark", studyId] });
      setBenchmarkJsonError(null);
    },
    onError: (err) => setBenchmarkJsonError(err instanceof Error ? err.message : "Upload failed"),
  });

  if (isLoading) return <p className="text-[14px] text-ink-muted">Loading tasks…</p>;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
        {tasks && tasks.length > 0 && (
          <div className="flex flex-1 flex-col gap-3">
            {tasks.map((task) =>
              editingTaskId === task.id ? (
                <Card key={task.id}>
                  <TaskEditForm task={task} onDone={() => setEditingTaskId(null)} />
                </Card>
              ) : (
                <Card key={task.id}>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <span className="text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-tertiary">
                        Goal
                      </span>
                      <p className="mt-1.5 text-[15px] font-medium text-ink">{task.instruction}</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setEditingTaskId(task.id)}
                      className="shrink-0 text-[12px] font-medium text-ink-tertiary transition-colors hover:text-ink"
                    >
                      Edit
                    </button>
                  </div>
                  {task.starting_point && (
                    <div className="mt-3 border-t border-hairline pt-3">
                      <span className="text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-tertiary">
                        Starting point
                      </span>
                      <p className="mt-1 text-[13px] text-ink-muted">{task.starting_point}</p>
                    </div>
                  )}
                  <div className="mt-3 border-t border-hairline pt-3">
                    <span className="text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-tertiary">
                      Success condition
                    </span>
                    {readSuccessConditions(task).value ? (
                      <p className="mt-1 font-mono text-[13px] text-ink-muted">
                        {readSuccessConditions(task).key} = {readSuccessConditions(task).value}
                      </p>
                    ) : (
                      <p className="mt-1 text-[13px] text-semantic-warn">
                        Not set — simulations for this task will be rejected unless critical actions
                        are defined.
                      </p>
                    )}
                  </div>
                  {task.expected_critical_actions && task.expected_critical_actions.length > 0 && (
                    <div className="mt-3 border-t border-hairline pt-3">
                      <span className="text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-tertiary">
                        Critical actions
                      </span>
                      <p className="mt-1 font-mono text-[13px] text-ink-muted">
                        {task.expected_critical_actions.join(", ")}
                      </p>
                    </div>
                  )}
                </Card>
              )
            )}
          </div>
        )}

        {/* One task per study, per the current product design — the backend
        still supports several (a later A/B-across-tasks flow would need it),
        but the study builder only ever shows a single task's worth of setup. */}
        {(!tasks || tasks.length === 0) && (
        <Card className="flex-1">
          <CardTitle>Define the critical user task</CardTitle>
          <CardDescription className="mt-2">
            The business-relevant journey a participant attempts — e.g. &quot;add a running shoe
            under ₹5,000 to cart&quot;, not an arbitrary instruction.
          </CardDescription>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              createMutation.mutate();
            }}
            className="mt-4 flex flex-col gap-4"
          >
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="instruction">What should the participant accomplish?</Label>
              <Textarea
                id="instruction"
                rows={3}
                required
                placeholder="Transfer ₹2,000 to a saved beneficiary."
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="starting-point">Starting point (optional)</Label>
              <Input
                id="starting-point"
                placeholder="home_screen"
                value={startingPoint}
                onChange={(e) => setStartingPoint(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="success-value">Success condition</Label>
              <div className="flex gap-2">
                <Select
                  className="w-auto"
                  aria-label="Success condition type"
                  value={successKey}
                  onChange={(e) => setSuccessKey(e.target.value as SuccessKey)}
                >
                  {SUCCESS_KEYS.map((key) => (
                    <option key={key.value} value={key.value}>
                      {key.label}
                    </option>
                  ))}
                </Select>
                <Input
                  id="success-value"
                  placeholder="dashboard"
                  value={successValue}
                  onChange={(e) => setSuccessValue(e.target.value)}
                />
              </div>
              {(detected.entry || detected.success) && (
                <div className="flex flex-wrap items-center gap-2 rounded-md bg-surface-subtle px-3 py-2">
                  <span className="text-[12px] text-ink-muted">
                    Detected from your screens:{" "}
                    {detected.entry && (
                      <span className="font-mono">start {detected.entry}</span>
                    )}
                    {detected.entry && detected.success && " · "}
                    {detected.success && (
                      <span className="font-mono">finish {detected.success}</span>
                    )}
                  </span>
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => {
                      if (detected.entry) setStartingPoint(detected.entry);
                      if (detected.success) {
                        setSuccessKey("screen_key");
                        setSuccessValue(detected.success);
                      }
                    }}
                  >
                    Use these
                  </Button>
                </div>
              )}
              <p className="text-[12px] text-ink-tertiary">
                The task&apos;s finish line — reaching it is the only thing that marks a synthetic
                participant COMPLETED. Without this (or critical actions below) a run can only ever
                end in 100% drop-off, so starting one is rejected.
              </p>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="critical-actions">Critical actions (optional)</Label>
              <Input
                id="critical-actions"
                placeholder="add_to_cart, checkout_button"
                value={criticalActions}
                onChange={(e) => setCriticalActions(e.target.value)}
              />
              <p className="text-[12px] text-ink-tertiary">
                Milestones on the way to the finish line — used by the Analytics Engine&apos;s
                excess-actions/excess-screens friction metrics.
              </p>
            </div>
            {createMutation.isError && (
              <p className="text-[13px] text-semantic-warn">
                {createMutation.error instanceof Error
                  ? createMutation.error.message
                  : "Failed to create task"}
              </p>
            )}
            <Button type="submit" disabled={createMutation.isPending} className="self-start">
              {createMutation.isPending ? "Saving…" : "Save task"}
            </Button>
          </form>
        </Card>
        )}
      </div>

      <Card>
        <CardTitle>Human benchmark (optional)</CardTitle>
        <CardDescription className="mt-2">
          Real human task-outcome data for the same task — lets the Validation Engine report how
          closely the synthetic population&apos;s completion rate agrees with actual humans,
          instead of a bare, unbenchmarked number.
        </CardDescription>
        {benchmark && (
          <p className="mt-2 text-[12px] text-ink-tertiary">
            Version {benchmark.version} on file
            {benchmark.source ? ` · ${benchmark.source}` : ""}
            {typeof benchmark.task_outcomes?.completion_rate === "number"
              ? ` · ${(benchmark.task_outcomes.completion_rate * 100).toFixed(0)}% human completion rate`
              : ""}
          </p>
        )}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            benchmarkMutation.mutate();
          }}
          className="mt-4 flex flex-col gap-4"
        >
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="benchmark-source">Source</Label>
              <Input
                id="benchmark-source"
                placeholder="Pilot study, n=20"
                value={benchmarkSource}
                onChange={(e) => setBenchmarkSource(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="benchmark-completion-rate">Human completion rate</Label>
              <Input
                id="benchmark-completion-rate"
                type="number"
                min={0}
                max={1}
                step={0.01}
                placeholder="0.74"
                value={completionRate}
                onChange={(e) => setCompletionRate(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="benchmark-sample-size">Sample size</Label>
              <Input
                id="benchmark-sample-size"
                type="number"
                min={1}
                placeholder="20"
                value={sampleSize}
                onChange={(e) => setSampleSize(e.target.value)}
              />
            </div>
          </div>

          <details className="group rounded-md border border-hairline bg-surface-1/50 p-4">
            <summary className="cursor-pointer text-[13px] font-semibold text-ink-subtle">
              Advanced: interaction rates / segment labels / attention data (raw JSON)
            </summary>
            <div className="mt-3 flex flex-col gap-1.5">
              <Textarea
                rows={4}
                placeholder={
                  '{"interaction_rates": {"cta": 0.62}, "segment_labels": {...}, "attention_data": {...}}'
                }
                value={extraJson}
                onChange={(e) => setExtraJson(e.target.value)}
              />
            </div>
          </details>

          {benchmarkJsonError && (
            <p className="text-[13px] text-semantic-warn">{benchmarkJsonError}</p>
          )}
          <Button
            type="submit"
            variant="secondary"
            disabled={benchmarkMutation.isPending}
            className="self-start"
          >
            {benchmarkMutation.isPending
              ? "Saving…"
              : benchmark
                ? "Update benchmark"
                : "Upload benchmark"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
