import type { SelectHTMLAttributes } from "react";

export function Select({ className = "", ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={`w-full border border-hairline-strong bg-canvas px-3.5 py-2.5 text-[15px] text-ink focus:border-ink focus:outline-none ${className}`}
      {...props}
    />
  );
}
