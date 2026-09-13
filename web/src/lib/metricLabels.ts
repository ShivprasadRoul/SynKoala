// Humanizes app/services/analytics_engine.py's raw metric/segment names for
// display — a researcher (or the PM they hand this report to) should never
// have to read a snake_case identifier or a bare 0-1 float to understand a
// result.

type MetricFormat = "percent" | "ms" | "count";

interface MetricInfo {
  label: string;
  format: MetricFormat;
}

const METRIC_INFO: Record<string, MetricInfo> = {
  completion_rate: { label: "Completed the task", format: "percent" },
  abandonment_rate: { label: "Abandoned the task", format: "percent" },
  backtrack_rate: { label: "Backtracked at least once", format: "percent" },
  dead_end_rate: { label: "Got stuck with no way forward", format: "percent" },
  repeated_interaction_rate: {
    label: "Clicked the same thing repeatedly",
    format: "percent",
  },
  hesitation_time: {
    label: "Time spent hesitating before acting",
    format: "ms",
  },
  excess_actions: {
    label: "Extra actions beyond the shortest path",
    format: "count",
  },
  excess_screens: {
    label: "Extra screens visited beyond the shortest path",
    format: "count",
  },
  click_rate: { label: "Clicked on it", format: "percent" },
  revisit_rate: { label: "Looked at it more than once", format: "percent" },
  attention_share: { label: "Share of total attention", format: "percent" },
  first_attention_rate: {
    label: "First thing people noticed",
    format: "percent",
  },
  attention_dwell_ms: { label: "Average time spent looking", format: "ms" },
};

export function humanizeKey(key: string): string {
  const spaced = key.replace(/_/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

export function metricLabel(metric: string): string {
  return METRIC_INFO[metric]?.label ?? humanizeKey(metric);
}

export function formatMetricValue(
  metric: string,
  value: number | null,
): string {
  if (value === null) return "—";
  const format =
    METRIC_INFO[metric]?.format ?? (Math.abs(value) <= 1 ? "percent" : "count");
  if (format === "percent") return `${Math.round(value * 100)}%`;
  if (format === "ms") {
    return value >= 1000
      ? `${(value / 1000).toFixed(1)}s`
      : `${Math.round(value)}ms`;
  }
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

// "digital_confidence_high" -> "Digital confidence: High"
export function segmentLabel(segment: string): string {
  const match = segment.match(/^(.*)_(low|high)$/);
  if (!match) return humanizeKey(segment);
  const [, trait, bucket] = match;
  return `${humanizeKey(trait)}: ${bucket === "high" ? "High" : "Low"}`;
}
