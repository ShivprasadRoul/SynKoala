import type { HTMLAttributes } from "react";

export function Card({ className = "", ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`rounded-lg border border-hairline bg-surface-card p-6 shadow-card ${className}`}
      {...props}
    />
  );
}

export function CardTitle({ className = "", ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h2
      className={`font-display text-[17px] font-bold tracking-[-0.2px] text-ink ${className}`}
      {...props}
    />
  );
}

export function CardDescription({ className = "", ...props }: HTMLAttributes<HTMLParagraphElement>) {
  return <p className={`text-[13px] text-ink-muted ${className}`} {...props} />;
}
