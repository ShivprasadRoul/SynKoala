import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import {
  formatMetricValue,
  humanizeKey,
  metricLabel,
} from "@/lib/metricLabels";
import type { Metric, MetricsResponse } from "@/lib/types";

const LEVEL_LABELS: Record<keyof MetricsResponse, string> = {
  task_success: "Task success",
  friction: "Friction",
  discoverability: "Discoverability",
};

const LEVEL_BLURBS: Record<keyof MetricsResponse, string> = {
  task_success: "The headline number — did participants actually get it done?",
  friction:
    "Explains why success wasn't higher — backtracking, dead ends, repeated clicks.",
  discoverability:
    "Explains whether participants could find what the task needed.",
};

function completionHeadline(taskSuccess: Metric[]): string | null {
  const completion = taskSuccess.find(
    (m) => m.metric === "completion_rate" && m.value !== null,
  );
  if (!completion || completion.value === null) return null;
  const pct = Math.round(completion.value * 100);
  const n = completion.sample_size ?? 0;
  if (pct === 0) {
    return `Nobody completed the task — all ${n} participant${n === 1 ? "" : "s"} abandoned it.`;
  }
  if (pct === 100) {
    return `Every participant (${n} of ${n}) completed the task.`;
  }
  return `${pct}% of participants completed the task (${Math.round(completion.value * n)} of ${n}).`;
}

// PRD §7 / planning/12-web-app.md §8: this three-level breakdown is the results
// landing view, not the heatmap — task success is the headline, friction and
// discoverability explain why it isn't higher.
export function MetricsGrid({ metrics }: { metrics: MetricsResponse }) {
  const levels: (keyof MetricsResponse)[] = [
    "task_success",
    "friction",
    "discoverability",
  ];
  const hasAny = levels.some((level) => metrics[level].length > 0);

  if (!hasAny) {
    return (
      <EmptyState
        title="No metrics yet"
        description="Metrics are derived from participant observations once a run completes — this is expected until the Simulation Engine is wired up."
      />
    );
  }

  const headline = completionHeadline(metrics.task_success);

  return (
    <div className="flex flex-col gap-6">
      {headline && (
        <Card className="border-2 !border-ink/5 !bg-ink !text-canvas shadow-raised">
          <p className="text-[15px] font-semibold leading-snug">{headline}</p>
        </Card>
      )}
      <div className="grid gap-6 sm:grid-cols-3">
        {levels.map((level) => (
          <div key={level} className="flex flex-col gap-3">
            <div>
              <h3 className="text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-tertiary">
                {LEVEL_LABELS[level]}
              </h3>
              <p className="mt-1 text-[12px] text-ink-tertiary">
                {LEVEL_BLURBS[level]}
              </p>
            </div>
            <div className="flex flex-col gap-2">
              {metrics[level].length === 0 && (
                <p className="text-[13px] text-ink-tertiary">No data yet.</p>
              )}
              {[...metrics[level]]
                .sort((a, b) => (b.value ?? 0) - (a.value ?? 0))
                .map((metric) => (
                  <MetricCard key={metric.id} metric={metric} />
                ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// A metric row is dimensioned by element or screen, so many rows share one
// `metric` name — without this the grid shows a dozen identical `click_rate`
// cards that look like nonsense rather than per-element measurements.
function dimensionOf(metric: Metric): string | null {
  const key = metric.element_key ?? metric.screen_key;
  return key ? humanizeKey(key) : null;
}

function MetricCard({ metric }: { metric: Metric }) {
  const dimension = dimensionOf(metric);
  const n = metric.sample_size;
  return (
    <Card className="p-4">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-[13px] text-ink-muted">
          {metricLabel(metric.metric)}
        </span>
        <span className="font-mono text-[22px] font-bold tabular-nums text-ink">
          {formatMetricValue(metric.metric, metric.value)}
        </span>
      </div>
      {dimension && (
        <p
          className="mt-1 truncate text-[12px] text-ink-tertiary"
          title={dimension}
        >
          {dimension}
        </p>
      )}
      {metric.segment && (
        <p className="mt-1 text-[12px] text-ink-tertiary">
          {humanizeKey(metric.segment)}
        </p>
      )}
      {n !== null && (
        <p className="mt-1 text-[11px] text-ink-tertiary">
          based on {n} participant{n === 1 ? "" : "s"}
        </p>
      )}
    </Card>
  );
}
