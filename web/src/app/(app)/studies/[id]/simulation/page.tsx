"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card, CardDescription, CardTitle } from "@/components/ui/Card";
import { Label } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { getAudience } from "@/lib/api/audiences";
import { createSimulationRun } from "@/lib/api/simulations";
import { listStimuli } from "@/lib/api/stimulus";
import { listTasks } from "@/lib/api/tasks";

function ReadinessItem({ label, done }: { label: string; done: boolean }) {
  return (
    <li className="flex items-center gap-2 text-[13px]">
      <span
        className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${
          done ? "bg-primary text-on-primary" : "bg-surface-2 text-ink-tertiary"
        }`}
        aria-hidden
      >
        {done ? "✓" : "–"}
      </span>
      <span className={done ? "text-ink" : "text-ink-tertiary"}>{label}</span>
    </li>
  );
}

export default function SimulationPage() {
  const { id: studyId } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: tasks } = useQuery({ queryKey: ["tasks", studyId], queryFn: () => listTasks(studyId) });
  const { data: audience } = useQuery({
    queryKey: ["audience", studyId],
    queryFn: () => getAudience(studyId),
  });
  const { data: stimuli } = useQuery({
    queryKey: ["stimuli", studyId],
    queryFn: () => listStimuli(studyId),
  });

  const hasAudience = Boolean(audience);
  const hasTask = Boolean(tasks && tasks.length > 0);
  const hasAnalyzedStimulus = Boolean(
    stimuli?.some((s) => s.screens.some((screen) => screen.elements.length > 0))
  );
  const isReady = hasAudience && hasTask && hasAnalyzedStimulus;

  const [taskId, setTaskId] = useState("");
  const [populationSize, setPopulationSize] = useState(50);
  const [seed, setSeed] = useState("");

  const runMutation = useMutation({
    mutationFn: () =>
      createSimulationRun(studyId, {
        population_size: populationSize,
        task_id: taskId || null,
        seed: seed ? Number(seed) : null,
      }),
    onSuccess: (run) => router.push(`/studies/${studyId}/results/${run.id}`),
  });

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="font-display text-[18px] font-bold text-ink">Run synthetic user simulation</h2>
        <p className="mt-1 text-[13px] text-ink-muted">
          Test how your audience is likely to experience this journey.
        </p>
      </div>

      <Card>
        <ul className="flex flex-col gap-2">
          <ReadinessItem label="Audience configured" done={hasAudience} />
          <ReadinessItem label="Task defined" done={hasTask} />
          <ReadinessItem label="Stimulus imported and analyzed" done={hasAnalyzedStimulus} />
        </ul>
      </Card>

      <Card className="max-w-[560px] border-2 border-ink/5 shadow-raised">
        <CardTitle>Simulation setup</CardTitle>
        <CardDescription className="mt-2">
          The study must be READY, with an audience population and a task already defined — the
          backend checks all of this and returns a clear error if something&apos;s missing.
        </CardDescription>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            runMutation.mutate();
          }}
          className="mt-5 flex flex-col gap-4"
        >
          {tasks && tasks.length > 1 && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="task">Task</Label>
              <Select
                id="task"
                required
                value={taskId}
                onChange={(e) => setTaskId(e.target.value)}
              >
                <option value="" disabled>
                  Select a task
                </option>
                {tasks.map((task) => (
                  <option key={task.id} value={task.id}>
                    {task.instruction}
                  </option>
                ))}
              </Select>
            </div>
          )}

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="population-size">Simulation size</Label>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setPopulationSize((n) => Math.max(1, n - 10))}
                className="flex h-10 w-10 items-center justify-center rounded-md border border-hairline bg-surface-card text-[16px] font-semibold text-ink shadow-sm transition-colors hover:bg-surface-1"
                aria-label="Decrease population size"
              >
                −
              </button>
              <input
                id="population-size"
                type="number"
                min={1}
                max={1000}
                value={populationSize}
                onChange={(e) => setPopulationSize(Number(e.target.value))}
                className="w-24 rounded-md border border-hairline bg-surface-card px-3 py-2.5 text-center font-mono text-[16px] font-semibold tabular-nums text-ink shadow-sm focus:border-primary-strong focus:outline-none focus:ring-2 focus:ring-primary/40"
              />
              <button
                type="button"
                onClick={() => setPopulationSize((n) => Math.min(1000, n + 10))}
                className="flex h-10 w-10 items-center justify-center rounded-md border border-hairline bg-surface-card text-[16px] font-semibold text-ink shadow-sm transition-colors hover:bg-surface-1"
                aria-label="Increase population size"
              >
                +
              </button>
              <span className="text-[13px] text-ink-tertiary">synthetic participants</span>
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="seed">Seed (optional, for reproducibility)</Label>
            <input
              id="seed"
              type="number"
              value={seed}
              onChange={(e) => setSeed(e.target.value)}
              className="w-full rounded-md border border-hairline bg-surface-card px-3.5 py-2.5 text-[15px] text-ink shadow-sm focus:border-primary-strong focus:outline-none focus:ring-2 focus:ring-primary/40"
            />
          </div>

          {runMutation.isError && (
            <p className="text-[13px] text-semantic-warn">
              {runMutation.error instanceof Error
                ? runMutation.error.message
                : "Failed to start the run"}
            </p>
          )}
          <Button
            type="submit"
            disabled={runMutation.isPending}
            className="mt-1 w-full py-3.5 text-[15px]"
            title={isReady ? undefined : "Some setup is still missing — the backend will confirm exactly what"}
          >
            {runMutation.isPending ? "Starting…" : "Run simulation →"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
