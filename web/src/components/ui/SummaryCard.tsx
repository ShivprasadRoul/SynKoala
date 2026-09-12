import Link from "next/link";
import type { ReactNode } from "react";

import { Card } from "./Card";

type Status = "done" | "pending" | "empty";

const STATUS_DOT: Record<Status, string> = {
  done: "bg-primary",
  pending: "bg-semantic-warn",
  empty: "bg-surface-3",
};

interface Props {
  eyebrow: string;
  title: string;
  description?: ReactNode;
  status: Status;
  href: string;
  cta: string;
}

// One workflow stage's status, summarized as a card — used on the Overview
// dashboard so a researcher can see what's configured, what's missing, and
// where to go next without opening every tab.
export function SummaryCard({ eyebrow, title, description, status, href, cta }: Props) {
  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <span className={`h-1.5 w-1.5 rounded-full ${STATUS_DOT[status]}`} />
        <span className="text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-tertiary">
          {eyebrow}
        </span>
      </div>
      <div>
        <h3 className="font-display text-[16px] font-bold leading-snug text-ink">{title}</h3>
        {description && <div className="mt-1.5 text-[13px] text-ink-muted">{description}</div>}
      </div>
      <Link
        href={href}
        className="mt-auto inline-flex w-fit items-center gap-1 pt-1 text-[13px] font-semibold text-ink transition-colors hover:text-primary-deep"
      >
        {cta} <span aria-hidden>→</span>
      </Link>
    </Card>
  );
}
