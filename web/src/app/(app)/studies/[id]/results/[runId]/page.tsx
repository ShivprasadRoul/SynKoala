"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useState } from "react";

import { MetricsGrid } from "@/components/MetricsGrid";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { listParticipants } from "@/lib/api/audiences";
import {
  getInsights,
  getParticipantRuns,
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
import {
  formatMetricValue,
  humanizeKey,
  metricLabel,
} from "@/lib/metricLabels";
import type { Participant, Screen } from "@/lib/types";

function personaSummary(participant: Participant | undefined): string | null {
  const persona = participant?.persona;
  if (!persona) return null;
  const confidence = Math.round(persona.context.digital_confidence * 100);
  return `${persona.identity.name}, ${persona.identity.age} · ${persona.identity.occupation} · ${confidence}% digital confidence`;
}

const POLL_INTERVAL_MS = 3000;

const TABS = [
  "Summary",
  "Heatmap",
  "Scanpaths",
  "Segments",
  "Insights",
] as const;
type Tab = (typeof TABS)[number];

const SEVERITY_TONE: Record<string, string> = {
  high: "border-semantic-warn/40 bg-[color-mix(in_srgb,var(--color-semantic-warn)_10%,var(--color-surface-card))]",
  medium: "border-hairline-strong bg-surface-1",
  low: "border-hairline bg-surface-card",
};

function screenLookup(
  stimuli: { screens: Screen[] }[] | undefined,
): Map<string, Screen> {
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

  if (!cells)
    return <p className="text-[13px] text-ink-muted">Loading heatmap…</p>;
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
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {[...byScreen.entries()].map(([screenId, screenCells]) => {
        const screen = screens.get(screenId);
        return (
          <Card key={screenId} className="p-3">
            <p
              className="mb-2 truncate text-[13px] font-semibold text-ink"
              title={screen?.screen_key}
            >
              {screen ? humanizeKey(screen.screen_key) : screenId}
            </p>
            {/* No forced aspect ratio here — the image sets its own height
            (h-auto), so a portrait mobile screenshot renders whole instead of
            being cropped into a fixed 16:9 box. Heatmap x/y are already
            fractions of the screen (Analytics Engine's own normalization),
            so percentage positioning lines up regardless of the image's
            actual pixel size. */}
            <div className="relative w-full overflow-hidden rounded-md bg-surface-2">
              {screen?.image_url && (
                // eslint-disable-next-line @next/next/no-img-element -- external Supabase Storage URL
                <img
                  src={screen.image_url}
                  alt={screen.screen_key}
                  className="block h-auto w-full"
                />
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
                    background:
                      "radial-gradient(circle, rgba(220,38,38,0.9) 0%, rgba(220,38,38,0) 70%)",
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

// GAZE dominates a scan-gated screen's event stream (up to MAX_SCAN_ATTEMPTS
// samples before a persona notices the intended element) — rendering every
// one as a numbered badge is what made the old view an illegible cluster of
// 80+ overlapping labels. Only a real action is a decision worth numbering;
// gaze becomes small unlabeled dots, already covered at the population level
// by the Heatmap tab.
const ACTION_TYPES = new Set(["CLICK", "TAP", "OPEN", "SELECT", "BACK"]);

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
  // Which persona this scanpath belongs to — a scanpath alone is just dots
  // and clicks; knowing it's "Priya, 24, student, 30% digital confidence"
  // is what makes a dead end or a fast completion legible as a finding
  // rather than an anonymous trace.
  const { data: participantRuns } = useQuery({
    queryKey: ["participant-runs", runId],
    queryFn: () => getParticipantRuns(runId),
  });
  const { data: participants } = useQuery({
    queryKey: ["participants", studyId],
    queryFn: () => listParticipants(studyId),
  });
  const participantByRunId = new Map(
    (participantRuns ?? []).map((pr) => [
      pr.id,
      (participants ?? []).find((p) => p.id === pr.participant_id),
    ]),
  );
  const [selected, setSelected] = useState(0);
  // screen.width/height come back null for a screenshot upload (only a Figma
  // import extracts them) — the rendered <img>'s own natural size is the only
  // reliable coordinate space to normalize a step's raw pixel x/y against.
  const [naturalSizes, setNaturalSizes] = useState<
    Record<string, { width: number; height: number }>
  >({});

  if (!scanpaths)
    return <p className="text-[13px] text-ink-muted">Loading scanpaths…</p>;
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
        {scanpaths.map((p, index) => {
          const persona = participantByRunId.get(p.participant_run_id)?.persona;
          return (
            <button
              key={p.participant_run_id}
              type="button"
              onClick={() => setSelected(index)}
              title={
                personaSummary(participantByRunId.get(p.participant_run_id)) ??
                undefined
              }
              className={`rounded-md px-3 py-1.5 text-[12px] font-medium transition-colors ${
                index === selected
                  ? "bg-ink text-canvas"
                  : "bg-surface-2 text-ink-muted hover:bg-surface-1"
              }`}
            >
              {persona ? persona.identity.name : `Participant ${index + 1}`}
            </button>
          );
        })}
      </div>
      {personaSummary(
        participantByRunId.get(participant.participant_run_id),
      ) && (
        <p className="text-[13px] font-medium text-ink">
          {personaSummary(
            participantByRunId.get(participant.participant_run_id),
          )}
        </p>
      )}
      <p className="text-[12px] text-ink-tertiary">
        Small dots are glances; numbered markers are the actions this
        participant actually took, in order.
      </p>

      <div className="flex flex-col gap-4">
        {segments.map((segment, segIndex) => {
          const screen = screens.get(segment.screenId);
          const natural = naturalSizes[segment.screenId];
          const width = screen?.width || natural?.width || 390;
          const height = screen?.height || natural?.height || 844;
          const actionSteps = segment.steps.filter(
            (s) => s.x !== null && s.y !== null && ACTION_TYPES.has(s.type),
          );
          const gazeSteps = segment.steps.filter(
            (s) => s.x !== null && s.y !== null && !ACTION_TYPES.has(s.type),
          );
          // Consecutive actions on the same element collapse into one marker
          // with a "×N" count — a dead end (nothing to click through to)
          // reads as the participant clicking the same button repeatedly,
          // which used to render as a dozen overlapping numbered badges on
          // top of each other instead of one legible "clicked this 12 times."
          const actionGroups: {
            step: (typeof actionSteps)[number];
            count: number;
          }[] = [];
          for (const step of actionSteps) {
            const last = actionGroups.at(-1);
            if (last && last.step.element_id === step.element_id) {
              last.count += 1;
            } else {
              actionGroups.push({ step, count: 1 });
            }
          }
          return (
            <Card key={segIndex} className="mx-auto w-full max-w-sm p-3">
              <p
                className="mb-2 truncate text-[13px] font-semibold text-ink"
                title={screen?.screen_key}
              >
                {segIndex + 1}.{" "}
                {screen ? humanizeKey(screen.screen_key) : segment.screenId}
              </p>
              <div className="relative w-full overflow-hidden rounded-md bg-surface-2">
                {screen?.image_url && (
                  // eslint-disable-next-line @next/next/no-img-element -- external Supabase Storage URL
                  <img
                    src={screen.image_url}
                    alt={screen.screen_key}
                    className="block h-auto w-full"
                    onLoad={(e) => {
                      const img = e.currentTarget;
                      setNaturalSizes((prev) =>
                        prev[segment.screenId]
                          ? prev
                          : {
                              ...prev,
                              [segment.screenId]: {
                                width: img.naturalWidth,
                                height: img.naturalHeight,
                              },
                            },
                      );
                    }}
                  />
                )}
                {actionGroups.length > 1 && (
                  <svg
                    className="absolute inset-0 h-full w-full"
                    viewBox="0 0 100 100"
                    preserveAspectRatio="none"
                  >
                    <polyline
                      points={actionGroups
                        .map(
                          ({ step: s }) =>
                            `${((s.x as number) / width) * 100},${((s.y as number) / height) * 100}`,
                        )
                        .join(" ")}
                      fill="none"
                      stroke="rgba(37,99,235,0.6)"
                      strokeWidth={0.6}
                      vectorEffect="non-scaling-stroke"
                    />
                  </svg>
                )}
                {gazeSteps.map((step, stepIndex) => (
                  <span
                    key={`gaze-${stepIndex}`}
                    className="absolute h-1.5 w-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-ink/25"
                    style={{
                      left: `${((step.x as number) / width) * 100}%`,
                      top: `${((step.y as number) / height) * 100}%`,
                    }}
                    title={`glanced · scan ${step.scan_number ?? "–"}`}
                  />
                ))}
                {actionGroups.map(({ step, count }, groupIndex) => (
                  <span
                    key={`action-${groupIndex}`}
                    className="absolute flex h-6 min-w-6 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-primary px-1 text-[9px] font-bold text-on-primary shadow-sm"
                    style={{
                      left: `${((step.x as number) / width) * 100}%`,
                      top: `${((step.y as number) / height) * 100}%`,
                    }}
                    title={count > 1 ? `${step.type} × ${count}` : step.type}
                  >
                    {groupIndex + 1}
                    {count > 1 && ` ×${count}`}
                  </span>
                ))}
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

  if (!segments)
    return <p className="text-[13px] text-ink-muted">Loading segments…</p>;
  if (segments.length === 0) {
    return (
      <EmptyState
        title="No segment comparisons yet"
        description="Computed once this run's participants have generated traits at both ends of a segment (e.g. digital_confidence_low vs. _high)."
      />
    );
  }

  // Pivot "<trait>_low"/"<trait>_high" rows into one low-vs-high comparison
  // per trait — a flat table of 20+ rows repeating the same trait name next
  // to a raw metric key was the exact clutter being reported; a researcher
  // (or the PM they hand this to) wants "do more confident users do better?"
  // answerable at a glance, not assembled by eye from a long list.
  type Cell = { value: number | null; sampleSize: number | null };
  const byTrait = new Map<
    string,
    { low: Map<string, Cell>; high: Map<string, Cell> }
  >();
  const metricOrder: string[] = [];
  for (const row of segments) {
    const match = row.segment.match(/^(.*)_(low|high)$/);
    if (!match) continue;
    const [, trait, bucket] = match;
    const entry = byTrait.get(trait) ?? { low: new Map(), high: new Map() };
    entry[bucket as "low" | "high"].set(row.metric, {
      value: row.value,
      sampleSize: row.sample_size,
    });
    byTrait.set(trait, entry);
    if (!metricOrder.includes(row.metric)) metricOrder.push(row.metric);
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      {[...byTrait.entries()].map(([trait, { low, high }]) => (
        <Card key={trait} className="overflow-x-auto p-0">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="border-b border-hairline text-left">
                <th className="px-4 py-2.5 font-semibold text-ink">
                  {humanizeKey(trait)}
                </th>
                <th className="px-4 py-2.5 font-medium text-ink-tertiary">
                  Low
                </th>
                <th className="px-4 py-2.5 font-medium text-ink-tertiary">
                  High
                </th>
              </tr>
            </thead>
            <tbody>
              {metricOrder
                .filter((metric) => low.has(metric) || high.has(metric))
                .map((metric) => (
                  <tr
                    key={metric}
                    className="border-b border-hairline last:border-0"
                  >
                    <td className="px-4 py-2.5 text-ink-muted">
                      {metricLabel(metric)}
                    </td>
                    <td className="px-4 py-2.5 font-mono tabular-nums text-ink">
                      {formatMetricValue(
                        metric,
                        low.get(metric)?.value ?? null,
                      )}
                    </td>
                    <td className="px-4 py-2.5 font-mono tabular-nums text-ink">
                      {formatMetricValue(
                        metric,
                        high.get(metric)?.value ?? null,
                      )}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </Card>
      ))}
    </div>
  );
}

function InsightsTab({ runId }: { runId: string }) {
  const { data: insights } = useQuery({
    queryKey: ["insights", runId],
    queryFn: () => getInsights(runId),
  });

  if (!insights)
    return <p className="text-[13px] text-ink-muted">Loading insights…</p>;
  if (insights.length === 0) {
    return (
      <EmptyState
        title="No insights yet"
        description="An insight is only kept once its cited evidence clears a minimum sample size — with too few participants, none may pass, which is correct behavior"
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
            <h3 className="text-[14px] font-semibold text-ink">
              {insight.title}
            </h3>
            <StatusBadge status={insight.severity.toUpperCase()} />
          </div>
          <p className="mt-2 text-[13px] text-ink-muted">{insight.summary}</p>
          {insight.recommendation && (
            <p className="mt-2 text-[13px] text-ink">
              <span className="font-semibold">Recommendation: </span>
              {insight.recommendation}
            </p>
          )}
          {insight.affected_segments &&
            insight.affected_segments.length > 0 && (
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
      query.state.data && isTerminalRunStatus(query.state.data.status)
        ? false
        : POLL_INTERVAL_MS,
  });

  const cancelMutation = useMutation({
    mutationFn: () => cancelSimulationRun(runId),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["simulation-run", runId] }),
  });

  const { data: metrics } = useQuery({
    queryKey: ["simulation-metrics", runId],
    queryFn: () => getMetrics(runId),
    refetchInterval:
      run && isTerminalRunStatus(run.status) ? false : POLL_INTERVAL_MS,
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
          <h2 className="mt-1 font-mono text-[13px] tabular-nums text-ink-muted">
            {run.id}
          </h2>
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
          Polling every {POLL_INTERVAL_MS / 1000}s — this run is still in
          progress.
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

      {tab === "Summary" &&
        (metrics ? <MetricsGrid metrics={metrics} /> : null)}
      {tab === "Heatmap" && studyId && (
        <HeatmapTab runId={runId} studyId={studyId} />
      )}
      {tab === "Scanpaths" && studyId && (
        <ScanpathsTab runId={runId} studyId={studyId} />
      )}
      {tab === "Segments" && <SegmentsTab runId={runId} />}
      {tab === "Insights" && <InsightsTab runId={runId} />}
    </div>
  );
}
