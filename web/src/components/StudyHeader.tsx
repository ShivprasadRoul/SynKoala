"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/Button";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { getAudience } from "@/lib/api/audiences";
import { publishStudy } from "@/lib/api/simulations";
import { deleteStudy } from "@/lib/api/studies";
import { listStimuli } from "@/lib/api/stimulus";
import { listTasks } from "@/lib/api/tasks";
import { taskHasFinishLine } from "@/lib/taskReadiness";
import type { Study } from "@/lib/types";

const STATUS_LABELS: Record<string, string> = { DRAFT: "Draft", READY: "Published" };

function relativeTime(iso: string): string {
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

// The study's identity + lifecycle state, shown above the workflow stepper on
// every tab. Publish lives here (not buried in the Overview tab) since it's a
// study-wide action: one click both marks the study READY and starts its
// first simulation run (SimulationUseCase.publish) — replacing the old
// "PATCH status=READY" flow, which only flipped a status flag and never
// actually ran anything. The backend re-validates everything on its own
// (and is the actual source of truth for canPublish's messages via
// publish.isError below); these three queries just let the button start
// disabled instead of failing only after a click.
export function StudyHeader({ study }: { study: Study }) {
  const queryClient = useQueryClient();
  const router = useRouter();
  const { data: audience } = useQuery({
    queryKey: ["audience", study.id],
    queryFn: () => getAudience(study.id),
  });
  const { data: tasks } = useQuery({
    queryKey: ["tasks", study.id],
    queryFn: () => listTasks(study.id),
  });
  const { data: stimuli } = useQuery({
    queryKey: ["stimuli", study.id],
    queryFn: () => listStimuli(study.id),
  });

  const publish = useMutation({
    mutationFn: () => publishStudy(study.id),
    onSuccess: (run) => {
      queryClient.invalidateQueries({ queryKey: ["study", study.id] });
      queryClient.invalidateQueries({ queryKey: ["simulationRuns", study.id] });
      router.push(`/studies/${study.id}/results/${run.id}`);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteStudy(study.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["studies"] });
      router.push("/dashboard");
    },
  });

  function handleDelete() {
    if (window.confirm(`Delete "${study.name}"? This can't be undone from the UI.`)) {
      deleteMutation.mutate();
    }
  }

  const hasAnalyzedStimulus = Boolean(
    stimuli?.some((stimulus) => stimulus.screens.some((screen) => screen.elements.length > 0))
  );
  const hasCompletableTask = Boolean(tasks?.some(taskHasFinishLine));
  const missingRequirement = !audience
    ? "an audience segment"
    : !hasCompletableTask
      ? "a task with a success condition or critical actions"
      : !hasAnalyzedStimulus
        ? "an analyzed stimulus"
        : !study.population_size
          ? "a sample size"
          : null;
  const canPublish = missingRequirement === null;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <Link
          href="/dashboard"
          className="inline-flex w-fit items-center gap-1.5 text-[13px] font-medium text-ink-muted transition-colors hover:text-ink"
        >
          <span aria-hidden>←</span> Studies
        </Link>
        <button
          type="button"
          onClick={handleDelete}
          disabled={deleteMutation.isPending}
          className="text-[12px] font-medium text-ink-tertiary transition-colors hover:text-semantic-warn"
        >
          {deleteMutation.isPending ? "Deleting…" : "Delete study"}
        </button>
      </div>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-[26px] font-extrabold tracking-[-0.4px] text-ink">
            {study.name}
          </h1>
          {study.objective && (
            <p className="mt-1.5 max-w-[560px] text-[14px] text-ink-muted">{study.objective}</p>
          )}
          <div className="mt-3 flex flex-wrap items-center gap-2 text-[12px] text-ink-tertiary">
            <StatusBadge status={study.status} label={STATUS_LABELS[study.status]} />
            <span>
              {study.population_size ?? "No"} synthetic {study.population_size === 1 ? "user" : "users"}
            </span>
            <span aria-hidden>·</span>
            <span>Last edited {relativeTime(study.updated_at)}</span>
          </div>
        </div>

        {study.status === "DRAFT" && (
          <div className="flex flex-col items-end gap-1.5">
            <Button
              disabled={publish.isPending || !canPublish}
              title={canPublish ? undefined : `Add ${missingRequirement} before publishing this study`}
              onClick={() => publish.mutate()}
            >
              {publish.isPending ? "Publishing…" : "Publish & Run Simulation"}
            </Button>
            {!canPublish && (
              <p className="text-[12px] text-ink-tertiary">Needs {missingRequirement}</p>
            )}
          </div>
        )}
      </div>

      {publish.isError && (
        <p className="text-[13px] text-semantic-warn">
          {publish.error instanceof Error ? publish.error.message : "Couldn't update the study"}
        </p>
      )}
      {deleteMutation.isError && (
        <p className="text-[13px] text-semantic-warn">
          {deleteMutation.error instanceof Error
            ? deleteMutation.error.message
            : "Couldn't delete the study"}
        </p>
      )}
    </div>
  );
}
