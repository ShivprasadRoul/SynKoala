import type { ButtonHTMLAttributes } from "react";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost";
}

const VARIANT_CLASSES: Record<NonNullable<Props["variant"]>, string> = {
  primary: "bg-primary text-on-primary shadow-sm hover:bg-primary-strong",
  secondary:
    "border border-hairline-strong bg-surface-card text-ink shadow-sm hover:border-ink hover:bg-surface-1",
  ghost: "text-ink-muted hover:bg-surface-1 hover:text-ink",
};

export function Button({ variant = "primary", className = "", ...props }: Props) {
  return (
    <button
      className={`rounded-md px-5 py-2.5 text-[14px] font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${VARIANT_CLASSES[variant]} ${className}`}
      {...props}
    />
  );
}
