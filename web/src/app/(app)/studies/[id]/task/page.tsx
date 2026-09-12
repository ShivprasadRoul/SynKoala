"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card, CardDescription, CardTitle } from "@/components/ui/Card";
import { Input, Label, Textarea } from "@/components/ui/Input";
import { createTask, listTasks } from "@/lib/api/tasks";

export default function TaskPage() {
  const { id: studyId } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const { data: tasks, isLoading } = useQuery({
    queryKey: ["tasks", studyId],
    queryFn: () => listTasks(studyId),
  });

  const [instruction, setInstruction] = useState("");
  const [startingPoint, setStartingPoint] = useState("");

  const createMutation = useMutation({
    mutationFn: () =>
      createTask(studyId, { instruction, starting_point: startingPoint || null }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks", studyId] });
      setInstruction("");
      setStartingPoint("");
    },
  });

  if (isLoading) return <p className="text-[14px] text-ink-muted">Loading tasks…</p>;

  return (
    <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
      {tasks && tasks.length > 0 && (
        <div className="flex flex-1 flex-col gap-3">
          {tasks.map((task) => (
            <Card key={task.id}>
              <span className="text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-tertiary">
                Goal
              </span>
              <p className="mt-1.5 text-[15px] font-medium text-ink">{task.instruction}</p>
              {task.starting_point && (
                <div className="mt-3 border-t border-hairline pt-3">
                  <span className="text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-tertiary">
                    Starting point
                  </span>
                  <p className="mt-1 text-[13px] text-ink-muted">{task.starting_point}</p>
                </div>
              )}
            </Card>
          ))}
        </div>
      )}

      <Card className="flex-1">
        <CardTitle>
          {tasks && tasks.length > 0 ? "Add another task" : "Define the critical user task"}
        </CardTitle>
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
    </div>
  );
}
