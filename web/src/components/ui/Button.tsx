import type { ButtonHTMLAttributes } from "react";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost";
}

const VARIANT_CLASSES: Record<NonNullable<Props["variant"]>, string> = {
  primary: "bg-primary text-on-primary hover:bg-primary-strong",
  secondary: "border border-hairline-strong text-ink hover:border-ink",
  ghost: "text-ink-muted hover:text-ink",
};

export function Button({ variant = "primary", className = "", ...props }: Props) {
  return (
    <button
      className={`px-5 py-2.5 text-[14px] font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${VARIANT_CLASSES[variant]} ${className}`}
      {...props}
    />
  );
}
