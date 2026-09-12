import { bandLabel } from "@/lib/personaBands";
import type { GeneratedPersona } from "@/lib/types";

const BAND_CHIP_CLASSES: Record<ReturnType<typeof bandLabel>, string> = {
  Low: "bg-surface-2 text-ink-muted",
  Medium: "bg-[color-mix(in_srgb,var(--color-semantic-info)_14%,var(--color-canvas))] text-semantic-info",
  High: "bg-primary-soft text-primary-deep",
};

function BandChip({ label, value }: { label: string; value: number }) {
  const band = bandLabel(value);
  return (
    <div className={`rounded-md px-2.5 py-1.5 ${BAND_CHIP_CLASSES[band]}`}>
      <p className="text-[10px] font-bold uppercase tracking-[0.04em]">{band}</p>
      <p className="text-[11px] leading-tight opacity-80">{label}</p>
    </div>
  );
}

interface Props {
  persona: GeneratedPersona;
  onView: () => void;
}

export function PersonaCard({ persona, onView }: Props) {
  const { identity, behavior, context } = persona;
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-hairline bg-surface-card p-4 shadow-card">
      <span className="font-mono text-[11px] tabular-nums text-ink-tertiary">
        {persona.persona_id}
      </span>
      <div>
        <p className="font-display text-[15px] font-bold text-ink">{identity.name}</p>
        <p className="text-[12px] text-ink-muted">
          {identity.age} · {identity.occupation}
        </p>
        <p className="text-[12px] text-ink-tertiary">{identity.location}</p>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <BandChip label="Digital confidence" value={context.digital_confidence} />
        <BandChip label="Product familiarity" value={context.product_familiarity} />
        <BandChip label="Goal directedness" value={behavior.goal_directedness} />
        <BandChip label="Patience" value={behavior.patience} />
      </div>
      <button
        type="button"
        onClick={onView}
        className="mt-1 text-[13px] font-semibold text-ink transition-colors hover:text-primary-deep"
      >
        View persona <span aria-hidden>→</span>
      </button>
    </div>
  );
}
