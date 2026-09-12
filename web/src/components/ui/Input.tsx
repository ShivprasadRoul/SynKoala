import type { InputHTMLAttributes, LabelHTMLAttributes, TextareaHTMLAttributes } from "react";

export function Label({ className = "", ...props }: LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label
      className={`text-[13px] font-semibold uppercase tracking-[0.02em] text-ink-subtle ${className}`}
      {...props}
    />
  );
}

export function Input({ className = "", ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={`w-full border border-hairline-strong bg-canvas px-3.5 py-2.5 text-[15px] text-ink placeholder:text-ink-tertiary focus:border-ink focus:outline-none ${className}`}
      {...props}
    />
  );
}

export function Textarea({
  className = "",
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={`w-full border border-hairline-strong bg-canvas px-3.5 py-2.5 text-[15px] text-ink placeholder:text-ink-tertiary focus:border-ink focus:outline-none ${className}`}
      {...props}
    />
  );
}
