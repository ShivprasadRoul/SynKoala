import { TraitBar } from "@/components/persona/TraitBar";
import type { GeneratedPersona } from "@/lib/types";

// A few plain-language "likely to / less likely to" bullets, derived directly
// from this persona's own sampled numbers (thresholded at the same 0.6/0.4
// bands used elsewhere) — never invented text, so two personas with
// different traits genuinely read differently.
function interactionTendencies(persona: GeneratedPersona): { likely: string[]; lessLikely: string[] } {
  const { behavior, ui_preferences, friction } = persona;
  const likely: string[] = [];
  const lessLikely: string[] = [];

  if (ui_preferences.text_comprehension >= 0.6) likely.push("Look for explicit text CTAs");
  else lessLikely.push("Rely on explicit text CTAs");

  if (behavior.goal_directedness >= 0.6) likely.push("Follow a direct path to the goal");
  else likely.push("Explore before committing to a path");

  if (behavior.search_tendency >= 0.6) likely.push("Search rather than browse");
  else lessLikely.push("Use search to find things");

  if (friction.retry_probability >= 0.6) likely.push("Retry when blocked");
  else lessLikely.push("Retry after being blocked");

  if (behavior.exploration <= 0.4) lessLikely.push("Explore unrelated navigation");
  else likely.push("Explore unrelated navigation out of curiosity");

  if (ui_preferences.icon_only_cta_recognition <= 0.4) {
    lessLikely.push("Recognize icon-only actions without a label");
  }
  if (behavior.backtracking_tendency >= 0.6) likely.push("Backtrack when a path feels wrong");

  return { likely, lessLikely };
}

export function PersonaDetailModal({
  persona,
  onClose,
}: {
  persona: GeneratedPersona;
  onClose: () => void;
}) {
  const { identity, mental_model, goal, friction, ui_preferences } = persona;
  const { likely, lessLikely } = interactionTendencies(persona);

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-ink/40 px-4 py-10 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-[560px] rounded-lg border border-hairline bg-surface-card p-6 shadow-raised"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <span className="font-mono text-[11px] tabular-nums text-ink-tertiary">
              {persona.persona_id}
            </span>
            <h2 className="mt-1 font-display text-[20px] font-bold text-ink">{identity.name}</h2>
            <p className="text-[13px] text-ink-muted">
              {identity.age} · {identity.occupation} · {identity.location}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-md p-1.5 text-ink-tertiary transition-colors hover:bg-surface-1 hover:text-ink"
          >
            ✕
          </button>
        </div>

        <div className="mt-6 flex flex-col gap-3 border-t border-hairline pt-5">
          <h3 className="text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-tertiary">
            Behavioral profile
          </h3>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <TraitBar label="Digital confidence" value={persona.behavior.digital_confidence} />
            <TraitBar label="Exploration" value={persona.behavior.exploration} />
            <TraitBar label="Patience" value={persona.behavior.patience} />
            <TraitBar label="Goal directedness" value={persona.behavior.goal_directedness} />
          </div>
        </div>

        <div className="mt-5 flex flex-col gap-2 border-t border-hairline pt-5">
          <h3 className="text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-tertiary">
            Mental model
          </h3>
          <dl className="flex flex-col gap-2 text-[13px]">
            <div className="flex justify-between gap-3">
              <dt className="text-ink-tertiary">Expected action</dt>
              <dd className="text-right font-medium text-ink">{mental_model.expected_action}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-ink-tertiary">Expected location</dt>
              <dd className="text-right font-medium text-ink">{mental_model.expected_location}</dd>
            </div>
            {mental_model.expected_terminology.length > 0 && (
              <div className="flex flex-wrap justify-end gap-1.5">
                {mental_model.expected_terminology.map((term) => (
                  <span
                    key={term}
                    className="rounded-full bg-surface-1 px-2 py-0.5 text-[11px] text-ink-muted"
                  >
                    {term}
                  </span>
                ))}
              </div>
            )}
            <p className="text-[12px] text-ink-tertiary">{mental_model.navigation_expectation}</p>
          </dl>
        </div>

        <div className="mt-5 flex flex-col gap-1.5 border-t border-hairline pt-5">
          <h3 className="text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-tertiary">
            Goal
          </h3>
          <p className="text-[13px] font-medium text-ink">{goal.primary_goal}</p>
          <p className="text-[12px] text-ink-muted">{goal.motivation}</p>
        </div>

        <div className="mt-5 grid grid-cols-1 gap-5 border-t border-hairline pt-5 sm:grid-cols-2">
          <div>
            <h3 className="text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-tertiary">
              Friction behavior
            </h3>
            <div className="mt-2 flex flex-col gap-2">
              <TraitBar label="Retry probability" value={friction.retry_probability} />
              <TraitBar label="Abandonment threshold" value={friction.abandonment_threshold} />
              <TraitBar label="Help-seeking" value={friction.help_seeking_probability} />
            </div>
          </div>
          <div>
            <h3 className="text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-tertiary">
              UI preferences
            </h3>
            <div className="mt-2 flex flex-col gap-2">
              <TraitBar label="Text comprehension" value={ui_preferences.text_comprehension} />
              <TraitBar label="Icon reliance" value={ui_preferences.icon_reliance} />
              <TraitBar label="Scrolling tolerance" value={ui_preferences.scrolling_tolerance} />
            </div>
          </div>
        </div>

        <div className="mt-5 grid grid-cols-1 gap-4 border-t border-hairline pt-5 sm:grid-cols-2">
          <div>
            <h3 className="text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-tertiary">
              Likely to
            </h3>
            <ul className="mt-2 flex flex-col gap-1 text-[13px] text-ink">
              {likely.map((item) => (
                <li key={item}>• {item}</li>
              ))}
            </ul>
          </div>
          <div>
            <h3 className="text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-tertiary">
              Less likely to
            </h3>
            <ul className="mt-2 flex flex-col gap-1 text-[13px] text-ink-muted">
              {lessLikely.map((item) => (
                <li key={item}>• {item}</li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
