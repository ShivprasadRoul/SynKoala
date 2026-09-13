"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { Button } from "@/components/ui/Button";
import { Card, CardDescription, CardTitle } from "@/components/ui/Card";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { getAudience } from "@/lib/api/audiences";
import {
  createSimulationRun,
  isTerminalRunStatus,
  listSimulationRuns,
  publishStudy,
} from "@/lib/api/simulations";
import { getStudy } from "@/lib/api/studies";
import { listStimuli } from "@/lib/api/stimulus";
import { listTasks } from "@/lib/api/tasks";
import { taskHasFinishLine } from "@/lib/taskReadiness";
import type { SimulationRunSummary } from "@/lib/types";

const POLL_INTERVAL_MS = 3000;

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

function relativeTime(iso: string): string {
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

// Runs come back oldest-first (append-only, so position IS "Run #N" — no
// stored sequence column needed); this page wants newest-first for display.
function withRunNumbers(runs: SimulationRunSummary[]): (SimulationRunSummary & { runNumber: number })[] {
  return runs.map((run, index) => ({ ...run, runNumber: index + 1 })).reverse();
}

function RunRow({ studyId, run }: { studyId: string; run: SimulationRunSummary & { runNumber: number } }) {
  return (
    <Link
      href={`/studies/${studyId}/results/${run.id}`}
      className="flex items-center justify-between gap-3 rounded-md border border-hairline bg-surface-card px-4 py-3 transition-colors hover:bg-surface-1"
    >
      <div>
        <div className="flex items-center gap-2">
          <span className="text-[13px] font-semibold text-ink">Run #{run.runNumber}</span>
          <StatusBadge status={run.status} />
        </div>
        <p className="mt-1 text-[12px] text-ink-tertiary">
          {run.population_size} participants · started {relativeTime(run.created_at)}
        </p>
      </div>
      {run.completion_rate !== null && (
        <span className="font-mono text-[13px] tabular-nums text-ink-muted">
          {Math.round(run.completion_rate * 100)}% completion
        </span>
      )}
    </Link>
  );
}

export default function SimulationPage() {
  const { id: studyId } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();

  const { data: study } = useQuery({ queryKey: ["study", studyId], queryFn: () => getStudy(studyId) });
  const { data: tasks } = useQuery({ queryKey: ["tasks", studyId], queryFn: () => listTasks(studyId) });
  const { data: audience } = useQuery({
    queryKey: ["audience", studyId],
    queryFn: () => getAudience(studyId),
  });
  const { data: stimuli } = useQuery({
    queryKey: ["stimuli", studyId],
    queryFn: () => listStimuli(studyId),
  });
  const { data: runs } = useQuery({
    queryKey: ["simulationRuns", studyId],
    queryFn: () => listSimulationRuns(studyId),
    refetchInterval: (query) => {
      const latest = query.state.data?.at(-1);
      return latest && !isTerminalRunStatus(latest.status) ? POLL_INTERVAL_MS : false;
    },
  });

  const hasAudience = Boolean(audience);
  const hasCompletableTask = Boolean(tasks?.some(taskHasFinishLine));
  const hasAnalyzedStimulus = Boolean(
    stimuli?.some((s) => s.screens.some((screen) => screen.elements.length > 0))
  );
  const hasSampleSize = Boolean(study?.population_size);
  const isReady = hasAudience && hasCompletableTask && hasAnalyzedStimulus && hasSampleSize;

  const publishMutation = useMutation({
    mutationFn: () => publishStudy(studyId),
    onSuccess: (run) => {
      queryClient.invalidateQueries({ queryKey: ["study", studyId] });
      queryClient.invalidateQueries({ queryKey: ["simulationRuns", studyId] });
      router.push(`/studies/${studyId}/results/${run.id}`);
    },
  });

  // "Run again" against an already-published study — no population_size in
  // the body, SimulationUseCase.create_run defaults it from the study.
  const runAgainMutation = useMutation({
    mutationFn: () => createSimulationRun(studyId),
    onSuccess: (run) => {
      queryClient.invalidateQueries({ queryKey: ["simulationRuns", studyId] });
      router.push(`/studies/${studyId}/results/${run.id}`);
    },
  });

  if (!study || !runs) return <p className="text-[14px] text-ink-muted">Loading…</p>;

  if (runs.length === 0) {
    return (
      <div className="flex flex-col gap-6">
        <div>
          <h2 className="font-display text-[18px] font-bold text-ink">Ready to publish</h2>
          <p className="mt-1 text-[13px] text-ink-muted">
            Publishing starts this study&apos;s first simulation automatically, using its
            configured sample size — no need to set it again here.
          </p>
        </div>

        <Card>
          <ul className="flex flex-col gap-2">
            <ReadinessItem label="Audience configured" done={hasAudience} />
            <ReadinessItem label="Task has a success condition" done={hasCompletableTask} />
            <ReadinessItem label="Stimulus imported and analyzed" done={hasAnalyzedStimulus} />
            <ReadinessItem
              label={`${study.population_size ?? "No"} synthetic participants configured`}
              done={hasSampleSize}
            />
          </ul>
        </Card>

        <Card className="max-w-[420px] border-2 border-ink/5 shadow-raised">
          <CardTitle>Participants</CardTitle>
          <CardDescription className="mt-2">
            {study.population_size ?? "No"} synthetic users, set when this study was created.
          </CardDescription>
          {publishMutation.isError && (
            <p className="mt-3 text-[13px] text-semantic-warn">
              {publishMutation.error instanceof Error
                ? publishMutation.error.message
                : "Failed to publish this study"}
            </p>
          )}
          <Button
            className="mt-4 w-full py-3.5 text-[15px]"
            disabled={publishMutation.isPending || !isReady}
            title={isReady ? undefined : "Some setup is still missing — see the checklist above"}
            onClick={() => publishMutation.mutate()}
          >
            {publishMutation.isPending ? "Publishing…" : "Publish & Run Simulation →"}
          </Button>
        </Card>
      </div>
    );
  }

  const numbered = withRunNumbers(runs);
  const [latest, ...previous] = numbered;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display text-[18px] font-bold text-ink">Simulation runs</h2>
          <p className="mt-1 text-[13px] text-ink-muted">
            {study.population_size ?? "No"} synthetic participants configured for this study.
          </p>
        </div>
        <Button
          variant="secondary"
          disabled={runAgainMutation.isPending || !isTerminalRunStatus(latest.status)}
          title={
            isTerminalRunStatus(latest.status) ? undefined : "Wait for the current run to finish"
          }
          onClick={() => runAgainMutation.mutate()}
        >
          {runAgainMutation.isPending ? "Starting…" : "Run again"}
        </Button>
      </div>

      {runAgainMutation.isError && (
        <p className="text-[13px] text-semantic-warn">
          {runAgainMutation.error instanceof Error
            ? runAgainMutation.error.message
            : "Failed to start a new run"}
        </p>
      )}

      <Card className="border-2 border-ink/5 shadow-raised">
        <span className="text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-tertiary">
          Latest — Run #{latest.runNumber}
        </span>
        <div className="mt-2 flex items-center gap-3">
          <StatusBadge status={latest.status} />
          <span className="text-[13px] text-ink-muted">{latest.population_size} participants</span>
          {latest.completion_rate !== null && (
            <span className="font-mono text-[13px] tabular-nums text-ink-muted">
              {Math.round(latest.completion_rate * 100)}% completion
            </span>
          )}
        </div>
        <Link
          href={`/studies/${studyId}/results/${latest.id}`}
          className="mt-4 inline-flex text-[13px] font-semibold text-primary-deep hover:underline"
        >
          {isTerminalRunStatus(latest.status) ? "View results" : "View progress"} →
        </Link>
      </Card>

      {previous.length > 0 && (
        <div className="flex flex-col gap-2">
          <span className="text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-tertiary">
            Previous runs
          </span>
          {previous.map((run) => (
            <RunRow key={run.id} studyId={studyId} run={run} />
          ))}
        </div>
      )}
    </div>
  );
}
