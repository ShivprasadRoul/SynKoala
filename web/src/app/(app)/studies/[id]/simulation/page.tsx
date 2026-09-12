"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { Input, Label } from "@/components/ui/Input";
import { createSimulationRun } from "@/lib/api/simulations";
import { listTasks } from "@/lib/api/tasks";

export default function SimulationPage() {
  const { id: studyId } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: tasks } = useQuery({ queryKey: ["tasks", studyId], queryFn: () => listTasks(studyId) });

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
    <Card className="max-w-[560px]">
      <CardTitle>Start a simulation run</CardTitle>
      <p className="mt-2 text-[13px] text-ink-muted">
        The study must be READY, with an audience population and a task already defined — the
        backend checks all of this and returns a clear error if something&apos;s missing.
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          runMutation.mutate();
        }}
        className="mt-4 flex flex-col gap-4"
      >
        {tasks && tasks.length > 1 && (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="task">Task</Label>
            <select
              id="task"
              required
              value={taskId}
              onChange={(e) => setTaskId(e.target.value)}
              className="w-full border border-hairline-strong bg-canvas px-3.5 py-2.5 text-[15px] text-ink focus:border-ink focus:outline-none"
            >
              <option value="" disabled>
                Select a task
              </option>
              {tasks.map((task) => (
                <option key={task.id} value={task.id}>
                  {task.instruction}
                </option>
              ))}
            </select>
          </div>
        )}
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="population-size">Population size</Label>
          <Input
            id="population-size"
            type="number"
            min={1}
            max={1000}
            value={populationSize}
            onChange={(e) => setPopulationSize(Number(e.target.value))}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="seed">Seed (optional, for reproducibility)</Label>
          <Input id="seed" type="number" value={seed} onChange={(e) => setSeed(e.target.value)} />
        </div>
        {runMutation.isError && (
          <p className="text-[13px] text-semantic-warn">
            {runMutation.error instanceof Error
              ? runMutation.error.message
              : "Failed to start the run"}
          </p>
        )}
        <Button type="submit" disabled={runMutation.isPending} className="self-start">
          {runMutation.isPending ? "Starting…" : "Start run"}
        </Button>
      </form>
    </Card>
  );
}
