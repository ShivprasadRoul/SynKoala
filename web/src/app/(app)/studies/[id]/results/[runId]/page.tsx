"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useState } from "react";

import { MetricsGrid } from "@/components/MetricsGrid";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { StatusBadge } from "@/components/ui/StatusBadge";
import {
  getInsights,
  getPixelHeatmap,
  getScanpaths,
  getSegments,
} from "@/lib/api/results";
import {
  cancelSimulationRun,
  getMetrics,
  getSimulationRun,
  isTerminalRunStatus,
} from "@/lib/api/simulations";
import { listStimuli } from "@/lib/api/stimulus";
import type { Screen } from "@/lib/types";

const POLL_INTERVAL_MS = 3000;

const TABS = ["Summary", "Heatmap", "Scanpaths", "Segments", "Insights"] as const;
type Tab = (typeof TABS)[number];

const SEVERITY_TONE: Record<string, string> = {
  high: "border-semantic-warn/40 bg-[color-mix(in_srgb,var(--color-semantic-warn)_10%,var(--color-surface-card))]",
  medium: "border-hairline-strong bg-surface-1",
  low: "border-hairline bg-surface-card",
};

function screenLookup(stimuli: { screens: Screen[] }[] | undefined): Map<string, Screen> {
  const map = new Map<string, Screen>();
  for (const stimulus of stimuli ?? []) {
    for (const screen of stimulus.screens) map.set(screen.id, screen);
  }
  return map;
}

function HeatmapTab({ runId, studyId }: { runId: string; studyId: string }) {
  const { data: cells } = useQuery({
    queryKey: ["heatmap", runId],
    queryFn: () => getPixelHeatmap(runId),
  });
  const { data: stimuli } = useQuery({
    queryKey: ["stimuli", studyId],
    queryFn: () => listStimuli(studyId),
  });
  const screens = screenLookup(stimuli);

  if (!cells) return <p className="text-[13px] text-ink-muted">Loading heatmap…</p>;
  if (cells.length === 0) {
    return (
      <EmptyState
        title="No heatmap yet"
        description="Renders once participants have looked at (GAZE'd on) a screen — check back once this run has progressed."
      />
    );
  }

  const byScreen = new Map<string, typeof cells>();
  for (const cell of cells) {
    const list = byScreen.get(cell.screen_id) ?? [];
    list.push(cell);
    byScreen.set(cell.screen_id, list);
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      {[...byScreen.entries()].map(([screenId, screenCells]) => {
        const screen = screens.get(screenId);
        return (
          <Card key={screenId} className="p-3">
            <p className="mb-2 truncate text-[13px] font-semibold text-ink" title={screen?.screen_key}>
              {screen?.screen_key ?? screenId}
            </p>
            <div className="relative aspect-video overflow-hidden rounded-md bg-surface-2">
              {screen?.image_url && (
                // eslint-disable-next-line @next/next/no-img-element -- external Supabase Storage URL
                <img src={screen.image_url} alt={screen.screen_key} className="h-full w-full object-cover" />
              )}
              {screenCells.map((cell, index) => (
                <span
                  key={index}
                  className="absolute -translate-x-1/2 -translate-y-1/2 rounded-full"
                  style={{
                    left: `${cell.x * 100}%`,
                    top: `${cell.y * 100}%`,
                    width: 28,
                    height: 28,
                    background: "radial-gradient(circle, rgba(220,38,38,0.9) 0%, rgba(220,38,38,0) 70%)",
                    opacity: Math.max(0.15, cell.intensity),
                  }}
                />
              ))}
            </div>
          </Card>
        );
      })}
    </div>
  );
}

function ScanpathsTab({ runId, studyId }: { runId: string; studyId: string }) {
  const { data: scanpaths } = useQuery({
    queryKey: ["scanpaths", runId],
    queryFn: () => getScanpaths(runId),
  });
  const { data: stimuli } = useQuery({
    queryKey: ["stimuli", studyId],
    queryFn: () => listStimuli(studyId),
  });
  const screens = screenLookup(stimuli);
  const [selected, setSelected] = useState(0);

  if (!scanpaths) return <p className="text-[13px] text-ink-muted">Loading scanpaths…</p>;
  if (scanpaths.length === 0) {
    return (
      <EmptyState
        title="No scanpaths yet"
        description="Renders once a sampled participant has produced GAZE/action events on a screen."
      />
    );
  }

  const participant = scanpaths[Math.min(selected, scanpaths.length - 1)];

  // Contiguous same-screen steps become one segment, so a multi-screen
  // journey renders as one screenshot per screen visited, in order, rather
  // than one giant list mixing coordinate spaces from different screens.
  const segments: { screenId: string; steps: typeof participant.path }[] = [];
  for (const step of participant.path) {
    const last = segments.at(-1);
    if (step.screen_id && last?.screenId === step.screen_id) {
      last.steps.push(step);
    } else if (step.screen_id) {
      segments.push({ screenId: step.screen_id, steps: [step] });
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap gap-2">
        {scanpaths.map((p, index) => (
          <button
            key={p.participant_run_id}
            type="button"
            onClick={() => setSelected(index)}
            className={`rounded-md px-3 py-1.5 text-[12px] font-medium transition-colors ${
              index === selected
                ? "bg-ink text-canvas"
                : "bg-surface-2 text-ink-muted hover:bg-surface-1"
            }`}
          >
            Participant {index + 1}
          </button>
        ))}
      </div>

      <div className="flex flex-col gap-4">
        {segments.map((segment, segIndex) => {
          const screen = screens.get(segment.screenId);
          const width = screen?.width || 390;
          const height = screen?.height || 844;
          return (
            <Card key={segIndex} className="p-3">
              <p className="mb-2 truncate text-[13px] font-semibold text-ink" title={screen?.screen_key}>
                {segIndex + 1}. {screen?.screen_key ?? segment.screenId}
              </p>
              <div className="relative aspect-video overflow-hidden rounded-md bg-surface-2">
                {screen?.image_url && (
                  // eslint-disable-next-line @next/next/no-img-element -- external Supabase Storage URL
                  <img
                    src={screen.image_url}
                    alt={screen.screen_key}
                    className="h-full w-full object-cover"
                  />
                )}
                <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none">
                  <polyline
                    points={segment.steps
                      .filter((s) => s.x !== null && s.y !== null)
                      .map((s) => `${((s.x as number) / width) * 100},${((s.y as number) / height) * 100}`)
                      .join(" ")}
                    fill="none"
                    stroke="rgba(37,99,235,0.7)"
                    strokeWidth={0.6}
                    vectorEffect="non-scaling-stroke"
                  />
                </svg>
                {segment.steps.map(
                  (step, stepIndex) =>
                    step.x !== null &&
                    step.y !== null && (
                      <span
                        key={stepIndex}
                        className="absolute flex h-5 w-5 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-primary text-[9px] font-bold text-on-primary shadow-sm"
                        style={{ left: `${(step.x / width) * 100}%`, top: `${(step.y / height) * 100}%` }}
                        title={`${step.type} · scan ${step.scan_number ?? "–"}`}
                      >
                        {step.sequence_no}
                      </span>
                    )
                )}
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

function SegmentsTab({ runId }: { runId: string }) {
  const { data: segments } = useQuery({
    queryKey: ["segments", runId],
    queryFn: () => getSegments(runId),
  });

  if (!segments) return <p className="text-[13px] text-ink-muted">Loading segments…</p>;
  if (segments.length === 0) {
    return (
      <EmptyState
        title="No segment comparisons yet"
        description="Computed once this run's participants have generated traits at both ends of a segment (e.g. digital_confidence_low vs. _high)."
      />
    );
  }

  return (
    <Card className="overflow-x-auto p-0">
      <table className="w-full text-[13px]">
        <thead>
          <tr className="border-b border-hairline text-left text-ink-tertiary">
            <th className="px-4 py-2.5 font-medium">Segment</th>
            <th className="px-4 py-2.5 font-medium">Metric</th>
            <th className="px-4 py-2.5 font-medium">Value</th>
            <th className="px-4 py-2.5 font-medium">n</th>
          </tr>
        </thead>
        <tbody>
          {segments.map((row) => (
            <tr key={row.id} className="border-b border-hairline last:border-0">
              <td className="px-4 py-2.5 text-ink">{row.segment}</td>
              <td className="px-4 py-2.5 text-ink-muted">{row.metric}</td>
              <td className="px-4 py-2.5 font-mono tabular-nums text-ink">{row.value ?? "—"}</td>
              <td className="px-4 py-2.5 font-mono tabular-nums text-ink-tertiary">
                {row.sample_size ?? "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

function InsightsTab({ runId }: { runId: string }) {
  const { data: insights } = useQuery({
    queryKey: ["insights", runId],
    queryFn: () => getInsights(runId),
  });

  if (!insights) return <p className="text-[13px] text-ink-muted">Loading insights…</p>;
  if (insights.length === 0) {
    return (
      <EmptyState
        title="No insights yet"
        description="An insight is only kept once its cited evidence clears a minimum sample size — with too few participants, none may pass, which is correct behavior, not a bug."
      />
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {insights.map((insight) => (
        <Card
          key={insight.id}
          className={`border ${SEVERITY_TONE[insight.severity] ?? SEVERITY_TONE.low}`}
        >
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-[14px] font-semibold text-ink">{insight.title}</h3>
            <StatusBadge status={insight.severity.toUpperCase()} />
          </div>
          <p className="mt-2 text-[13px] text-ink-muted">{insight.summary}</p>
          {insight.recommendation && (
            <p className="mt-2 text-[13px] text-ink">
              <span className="font-semibold">Recommendation: </span>
              {insight.recommendation}
            </p>
          )}
          {insight.affected_segments && insight.affected_segments.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {insight.affected_segments.map((segment) => (
                <span
                  key={segment}
                  className="rounded-full bg-surface-2 px-2 py-0.5 text-[11px] text-ink-tertiary"
                >
                  {segment}
                </span>
              ))}
            </div>
          )}
          {insight.evidence_strength && (
            <p className="mt-2 font-mono text-[11px] text-ink-tertiary">
              evidence: {JSON.stringify(insight.evidence_strength)}
            </p>
          )}
        </Card>
      ))}
    </div>
  );
}

export default function ResultsPage() {
  const { runId } = useParams<{ id: string; runId: string }>();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("Summary");

  const { data: run } = useQuery({
    queryKey: ["simulation-run", runId],
    queryFn: () => getSimulationRun(runId),
    refetchInterval: (query) =>
      query.state.data && isTerminalRunStatus(query.state.data.status) ? false : POLL_INTERVAL_MS,
  });

  const cancelMutation = useMutation({
    mutationFn: () => cancelSimulationRun(runId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["simulation-run", runId] }),
  });

  const { data: metrics } = useQuery({
    queryKey: ["simulation-metrics", runId],
    queryFn: () => getMetrics(runId),
    refetchInterval: run && isTerminalRunStatus(run.status) ? false : POLL_INTERVAL_MS,
  });

  const studyId = run?.study_id;

  if (!run) return <p className="text-[14px] text-ink-muted">Loading run…</p>;

  return (
    <div className="flex flex-col gap-6">
      <Card className="flex items-center justify-between">
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-tertiary">
            Simulation run
          </span>
          <h2 className="mt-1 font-mono text-[13px] tabular-nums text-ink-muted">{run.id}</h2>
          <p className="mt-1 font-mono text-[13px] tabular-nums text-ink-muted">
            population {run.population_size}
            {run.seed !== null && ` · seed ${run.seed}`}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={run.status} />
          {run.status === "RUNNING" && (
            <Button
              type="button"
              variant="secondary"
              disabled={cancelMutation.isPending}
              onClick={() => cancelMutation.mutate()}
            >
              {cancelMutation.isPending ? "Cancelling…" : "Cancel run"}
            </Button>
          )}
        </div>
      </Card>

      {cancelMutation.isError && (
        <p className="text-[13px] text-semantic-warn">
          {cancelMutation.error instanceof Error
            ? cancelMutation.error.message
            : "Failed to cancel the run"}
        </p>
      )}

      {!isTerminalRunStatus(run.status) && (
        <p className="text-[13px] text-ink-tertiary">
          Polling every {POLL_INTERVAL_MS / 1000}s — this run is still in progress.
        </p>
      )}

      <nav className="flex gap-1 overflow-x-auto border-b border-hairline">
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`shrink-0 border-b-2 px-3 py-2 text-[13px] font-medium transition-colors ${
              tab === t
                ? "border-ink text-ink"
                : "border-transparent text-ink-muted hover:text-ink"
            }`}
          >
            {t}
          </button>
        ))}
      </nav>

      {tab === "Summary" && (metrics ? <MetricsGrid metrics={metrics} /> : null)}
      {tab === "Heatmap" && studyId && <HeatmapTab runId={runId} studyId={studyId} />}
      {tab === "Scanpaths" && studyId && <ScanpathsTab runId={runId} studyId={studyId} />}
      {tab === "Segments" && <SegmentsTab runId={runId} />}
      {tab === "Insights" && <InsightsTab runId={runId} />}
    </div>
  );
}
