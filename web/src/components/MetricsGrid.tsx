import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import type { Metric, MetricsResponse } from "@/lib/types";

const LEVEL_LABELS: Record<keyof MetricsResponse, string> = {
  task_success: "Task success",
  friction: "Friction",
  discoverability: "Discoverability",
};

// PRD §7 / planning/12-web-app.md §8: this three-level breakdown is the results
// landing view, not the heatmap — task success is the headline, friction and
// discoverability explain why it isn't higher.
export function MetricsGrid({ metrics }: { metrics: MetricsResponse }) {
  const levels: (keyof MetricsResponse)[] = ["task_success", "friction", "discoverability"];
  const hasAny = levels.some((level) => metrics[level].length > 0);

  if (!hasAny) {
    return (
      <EmptyState
        title="No metrics yet"
        description="Metrics are derived from participant observations once a run completes — this is expected until the Simulation Engine is wired up."
      />
    );
  }

  return (
    <div className="grid gap-6 sm:grid-cols-3">
      {levels.map((level) => (
        <div key={level} className="flex flex-col gap-3">
          <h3 className="text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-tertiary">
            {LEVEL_LABELS[level]}
          </h3>
          <div className="flex flex-col gap-2">
            {metrics[level].length === 0 && (
              <p className="text-[13px] text-ink-tertiary">No data yet.</p>
            )}
            {metrics[level].map((metric) => (
              <MetricCard key={metric.id} metric={metric} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// A metric row is dimensioned by element or screen, so many rows share one
// `metric` name — without this the grid shows a dozen identical `click_rate`
// cards that look like nonsense rather than per-element measurements.
function dimensionOf(metric: Metric): string | null {
  return metric.element_key ?? metric.screen_key ?? null;
}

function MetricCard({ metric }: { metric: Metric }) {
  const dimension = dimensionOf(metric);
  return (
    <Card className="p-4">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-[13px] text-ink-muted">{metric.metric}</span>
        <span className="font-mono text-[22px] font-bold tabular-nums text-ink">
          {metric.value ?? "—"}
        </span>
      </div>
      {dimension && (
        <p className="mt-1 truncate font-mono text-[12px] text-ink-tertiary" title={dimension}>
          {dimension}
        </p>
      )}
      {metric.segment && <p className="mt-1 text-[12px] text-ink-tertiary">{metric.segment}</p>}
      {metric.sample_size !== null && (
        <p className="mt-1 font-mono text-[11px] tabular-nums text-ink-tertiary">
          n={metric.sample_size}
        </p>
      )}
    </Card>
  );
}
