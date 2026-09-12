import type { ReactNode } from "react";

interface Props {
  title: string;
  description: string;
  action?: ReactNode;
}

// A deliberate, explanatory placeholder for "nothing here yet" — never bare
// whitespace. Used wherever a workflow stage is waiting on a prior one.
export function EmptyState({ title, description, action }: Props) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-hairline-strong/50 bg-surface-1/60 px-8 py-12 text-center">
      <h3 className="font-display text-[16px] font-bold text-ink">{title}</h3>
      <p className="max-w-[420px] text-[13px] text-ink-muted">{description}</p>
      {action}
    </div>
  );
}
