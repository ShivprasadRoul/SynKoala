import type { HTMLAttributes } from "react";

export function Card({ className = "", ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={`border border-hairline bg-surface-1 p-6 ${className}`} {...props} />;
}

export function CardTitle({ className = "", ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h2
      className={`font-display text-[18px] font-bold tracking-[-0.2px] text-ink ${className}`}
      {...props}
    />
  );
}
