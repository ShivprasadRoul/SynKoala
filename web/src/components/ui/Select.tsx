import type { SelectHTMLAttributes } from "react";

export function Select({ className = "", ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={`w-full rounded-md border border-hairline bg-surface-card px-3.5 py-2.5 text-[15px] text-ink shadow-sm transition-colors focus:border-primary-strong focus:outline-none focus:ring-2 focus:ring-primary/40 ${className}`}
      {...props}
    />
  );
}
