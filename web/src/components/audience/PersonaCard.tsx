import { Card } from "@/components/ui/Card";
import type { Persona } from "@/lib/types";

function TagList({ label, items }: { label: string; items?: string[] }) {
  if (!items || items.length === 0) return null;
  return (
    <p className="mt-2 text-[13px] text-ink-muted">
      <span className="font-semibold text-ink-subtle">{label}:</span> {items.join(", ")}
    </p>
  );
}

export function PersonaCard({ persona }: { persona: Persona }) {
  return (
    <Card>
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="font-display text-[16px] font-bold text-ink">{persona.persona_name}</h3>
        <span className="text-[13px] text-ink-tertiary">
          {persona.age_group} · {persona.country}
        </span>
      </div>
      <p className="mt-1 text-[13px] text-ink-muted">{persona.subtitle}</p>
      {persona.persona_description && (
        <p className="mt-2 text-[13px] text-ink-muted">{persona.persona_description}</p>
      )}
      <TagList label="Motivations" items={persona.motivations} />
      <TagList label="Pain points" items={persona.pain_points} />
      <TagList label="Key decision triggers" items={persona.key_decision_trigger} />
      <TagList label="Preferred channels" items={persona.preferred_channels} />
    </Card>
  );
}
