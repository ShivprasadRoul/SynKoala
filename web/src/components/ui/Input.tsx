import type {
  HTMLAttributes,
  InputHTMLAttributes,
  LabelHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";

export function Label({ className = "", ...props }: LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label
      className={`text-[12px] font-semibold uppercase tracking-[0.04em] text-ink-tertiary ${className}`}
      {...props}
    />
  );
}

const FIELD_CLASSES =
  "w-full rounded-md border border-hairline bg-surface-card px-3.5 py-2.5 text-[15px] text-ink shadow-sm transition-colors placeholder:text-ink-tertiary focus:border-primary-strong focus:outline-none focus:ring-2 focus:ring-primary/40";

export function Input({ className = "", ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`${FIELD_CLASSES} ${className}`} {...props} />;
}

export function Textarea({
  className = "",
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={`${FIELD_CLASSES} ${className}`} {...props} />;
}

export function HelperText({ className = "", ...props }: HTMLAttributes<HTMLParagraphElement>) {
  return <p className={`text-[12px] text-ink-tertiary ${className}`} {...props} />;
}
