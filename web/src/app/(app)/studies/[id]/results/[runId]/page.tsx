"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";

import { MetricsGrid } from "@/components/MetricsGrid";
import { Card } from "@/components/ui/Card";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { getMetrics, getSimulationRun, isTerminalRunStatus } from "@/lib/api/simulations";

const POLL_INTERVAL_MS = 3000;

export default function ResultsPage() {
  const { runId } = useParams<{ id: string; runId: string }>();

  const { data: run } = useQuery({
    queryKey: ["simulation-run", runId],
    queryFn: () => getSimulationRun(runId),
    refetchInterval: (query) =>
      query.state.data && isTerminalRunStatus(query.state.data.status) ? false : POLL_INTERVAL_MS,
  });

  const { data: metrics } = useQuery({
    queryKey: ["simulation-metrics", runId],
    queryFn: () => getMetrics(runId),
    refetchInterval: run && isTerminalRunStatus(run.status) ? false : POLL_INTERVAL_MS,
  });

  if (!run) return <p className="text-[14px] text-ink-muted">Loading run…</p>;

  return (
    <div className="flex flex-col gap-6">
      <Card className="flex items-center justify-between">
        <div>
          <h2 className="font-display text-[16px] font-bold text-ink">Run {run.id}</h2>
          <p className="mt-1 font-mono text-[13px] tabular-nums text-ink-muted">
            population {run.population_size}
            {run.seed !== null && ` · seed ${run.seed}`}
          </p>
        </div>
        <StatusBadge status={run.status} />
      </Card>

      {!isTerminalRunStatus(run.status) && (
        <p className="text-[13px] text-ink-tertiary">
          Polling every {POLL_INTERVAL_MS / 1000}s. A run only completes once a worker processes
          it — until the Simulation Engine is wired up, this may stay RUNNING indefinitely.
        </p>
      )}

      {metrics && <MetricsGrid metrics={metrics} />}
    </div>
  );
}
