// The design system (SynKoala-Landing) defines exactly one chromatic accent (lime)
// plus two semantic hues (warn/info) — no error red. FAILED/CANCELLED stay a strong
// neutral rather than inventing a color outside that palette.
const TONE_CLASSES: Record<string, string> = {
  DRAFT: "bg-surface-2 text-ink-muted",
  PENDING: "bg-surface-2 text-ink-muted",
  READY: "bg-[color-mix(in_srgb,var(--color-semantic-info)_14%,var(--color-canvas))] text-semantic-info",
  RUNNING:
    "bg-[color-mix(in_srgb,var(--color-semantic-warn)_14%,var(--color-canvas))] text-semantic-warn",
  CANCELLING:
    "bg-[color-mix(in_srgb,var(--color-semantic-warn)_14%,var(--color-canvas))] text-semantic-warn",
  COMPLETED: "bg-primary-soft text-primary-deep",
  FAILED: "border border-hairline-strong bg-surface-3 text-ink",
  CANCELLED: "border border-hairline-strong bg-surface-3 text-ink",
};

export function StatusBadge({ status, label }: { status: string; label?: string }) {
  const classes = TONE_CLASSES[status] ?? "bg-surface-2 text-ink-muted";
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.04em] ${classes}`}
    >
      {label ?? status}
    </span>
  );
}
