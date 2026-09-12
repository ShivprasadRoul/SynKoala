"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Input, Label, Textarea } from "@/components/ui/Input";
import type { Persona } from "@/lib/types";

// Raw, editable form state — list/map fields stay as free text until submit, since
// typing a comma or a newline mid-edit shouldn't fight the input.
interface FormState {
  persona_name: string;
  subtitle: string;
  persona_description: string;
  age_group: string;
  country: string;
  language: string;
  occupation: string;
  generation: string;
  income_band: string;
  urbanicity: string;
  primary_device: string;
  product_usage: string;
  brand_affinity: string;
  lifestyle_behaviour: string;
  risk_tolerance: string;
  price_sensitivity: string;
  novelty_presence: string;
  emotional_state: string;
  purchase_occasion: string;
  decision_stage: string;
  job_to_be_done: string;
  motivationsText: string;
  painPointsText: string;
  keyDecisionTriggerText: string;
  preferredChannelsText: string;
  decisionCriteriaText: string;
  domainText: string;
}

const EMPTY_FORM: FormState = {
  persona_name: "",
  subtitle: "",
  persona_description: "",
  age_group: "",
  country: "",
  language: "",
  occupation: "",
  generation: "",
  income_band: "",
  urbanicity: "",
  primary_device: "",
  product_usage: "",
  brand_affinity: "",
  lifestyle_behaviour: "",
  risk_tolerance: "",
  price_sensitivity: "",
  novelty_presence: "",
  emotional_state: "",
  purchase_occasion: "",
  decision_stage: "",
  job_to_be_done: "",
  motivationsText: "",
  painPointsText: "",
  keyDecisionTriggerText: "",
  preferredChannelsText: "",
  decisionCriteriaText: "",
  domainText: "",
};

function splitList(text: string): string[] {
  return text
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

// "key: value" per line, e.g. "price: affordability\nbrand: trust" — no key-value
// editor exists elsewhere in this app yet, and this is the least-used field group.
function parseKeyValueLines(text: string): Record<string, string> {
  const map: Record<string, string> = {};
  for (const line of text.split("\n")) {
    const [key, ...rest] = line.split(":");
    const value = rest.join(":").trim();
    if (key?.trim() && value) map[key.trim()] = value;
  }
  return map;
}

function toPersona(form: FormState): Persona {
  const optional = <K extends keyof FormState>(key: K): string | undefined =>
    form[key] ? (form[key] as string) : undefined;

  return {
    persona_name: form.persona_name,
    subtitle: form.subtitle,
    age_group: form.age_group,
    country: form.country,
    language: form.language,
    persona_description: optional("persona_description"),
    occupation: optional("occupation"),
    generation: optional("generation"),
    income_band: optional("income_band"),
    urbanicity: optional("urbanicity"),
    primary_device: optional("primary_device"),
    product_usage: optional("product_usage"),
    brand_affinity: optional("brand_affinity"),
    lifestyle_behaviour: optional("lifestyle_behaviour"),
    risk_tolerance: optional("risk_tolerance"),
    price_sensitivity: optional("price_sensitivity"),
    novelty_presence: optional("novelty_presence"),
    emotional_state: optional("emotional_state"),
    purchase_occasion: optional("purchase_occasion"),
    decision_stage: optional("decision_stage"),
    job_to_be_done: optional("job_to_be_done"),
    motivations: splitList(form.motivationsText),
    pain_points: splitList(form.painPointsText),
    key_decision_trigger: splitList(form.keyDecisionTriggerText),
    preferred_channels: splitList(form.preferredChannelsText),
    decision_criteria: parseKeyValueLines(form.decisionCriteriaText),
    domain: parseKeyValueLines(form.domainText),
  };
}

interface Props {
  defaultCountry?: string;
  defaultLanguage?: string;
  onSubmit: (persona: Persona) => void;
  isPending: boolean;
  error: string | null;
}

export function PersonaForm({ defaultCountry, defaultLanguage, onSubmit, isPending, error }: Props) {
  const [form, setForm] = useState<FormState>({
    ...EMPTY_FORM,
    country: defaultCountry ?? "",
    language: defaultLanguage ?? "",
  });

  const set = <K extends keyof FormState>(key: K) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => setForm((prev) => ({ ...prev, [key]: e.target.value }));

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(toPersona(form));
      }}
      className="flex flex-col gap-4"
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="persona-name">Persona name</Label>
          <Input
            id="persona-name"
            required
            placeholder="Priya, the cautious first-time investor"
            value={form.persona_name}
            onChange={set("persona_name")}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="persona-subtitle">Subtitle</Label>
          <Input
            id="persona-subtitle"
            required
            placeholder="Tech-savvy Millennial"
            value={form.subtitle}
            onChange={set("subtitle")}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="persona-age-group">Age group</Label>
          <Input
            id="persona-age-group"
            required
            placeholder="25-30"
            pattern="^\d+(-\d+)?$"
            title="A single number (25) or a range (25-30)"
            value={form.age_group}
            onChange={set("age_group")}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="persona-country">Country</Label>
          <Input id="persona-country" required value={form.country} onChange={set("country")} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="persona-language">Language</Label>
          <Input id="persona-language" required value={form.language} onChange={set("language")} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="persona-occupation">Occupation</Label>
          <Input id="persona-occupation" value={form.occupation} onChange={set("occupation")} />
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="persona-description">Description</Label>
        <Textarea
          id="persona-description"
          rows={2}
          placeholder="Free-form notes about who this persona is and why they matter to this study."
          value={form.persona_description}
          onChange={set("persona_description")}
        />
      </div>

      <details className="border border-hairline p-4">
        <summary className="cursor-pointer text-[13px] font-semibold text-ink-subtle">
          More attributes (optional)
        </summary>
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="persona-generation">Generation</Label>
            <Input id="persona-generation" value={form.generation} onChange={set("generation")} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="persona-income-band">Income band</Label>
            <Input id="persona-income-band" value={form.income_band} onChange={set("income_band")} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="persona-urbanicity">Urbanicity</Label>
            <Input id="persona-urbanicity" value={form.urbanicity} onChange={set("urbanicity")} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="persona-primary-device">Primary device</Label>
            <Input
              id="persona-primary-device"
              value={form.primary_device}
              onChange={set("primary_device")}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="persona-product-usage">Product usage</Label>
            <Input
              id="persona-product-usage"
              value={form.product_usage}
              onChange={set("product_usage")}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="persona-brand-affinity">Brand affinity</Label>
            <Input
              id="persona-brand-affinity"
              value={form.brand_affinity}
              onChange={set("brand_affinity")}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="persona-lifestyle">Lifestyle & behaviour</Label>
            <Input
              id="persona-lifestyle"
              value={form.lifestyle_behaviour}
              onChange={set("lifestyle_behaviour")}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="persona-risk-tolerance">Risk tolerance</Label>
            <Input
              id="persona-risk-tolerance"
              value={form.risk_tolerance}
              onChange={set("risk_tolerance")}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="persona-price-sensitivity">Price sensitivity</Label>
            <Input
              id="persona-price-sensitivity"
              value={form.price_sensitivity}
              onChange={set("price_sensitivity")}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="persona-novelty-presence">Novelty / newness preference</Label>
            <Input
              id="persona-novelty-presence"
              value={form.novelty_presence}
              onChange={set("novelty_presence")}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="persona-emotional-state">Emotional state</Label>
            <Input
              id="persona-emotional-state"
              value={form.emotional_state}
              onChange={set("emotional_state")}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="persona-purchase-occasion">Purchase occasion</Label>
            <Input
              id="persona-purchase-occasion"
              value={form.purchase_occasion}
              onChange={set("purchase_occasion")}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="persona-decision-stage">Decision stage</Label>
            <Input
              id="persona-decision-stage"
              value={form.decision_stage}
              onChange={set("decision_stage")}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="persona-job-to-be-done">Job to be done</Label>
            <Input
              id="persona-job-to-be-done"
              value={form.job_to_be_done}
              onChange={set("job_to_be_done")}
            />
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="persona-motivations">Motivations (comma-separated)</Label>
            <Input
              id="persona-motivations"
              placeholder="save for retirement, avoid fees"
              value={form.motivationsText}
              onChange={set("motivationsText")}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="persona-pain-points">Pain points (comma-separated)</Label>
            <Input
              id="persona-pain-points"
              placeholder="confusing jargon, hidden charges"
              value={form.painPointsText}
              onChange={set("painPointsText")}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="persona-key-decision-trigger">Key decision triggers (comma-separated)</Label>
            <Input
              id="persona-key-decision-trigger"
              placeholder="a friend's recommendation"
              value={form.keyDecisionTriggerText}
              onChange={set("keyDecisionTriggerText")}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="persona-preferred-channels">Preferred channels (comma-separated)</Label>
            <Input
              id="persona-preferred-channels"
              placeholder="WhatsApp, in-app notifications"
              value={form.preferredChannelsText}
              onChange={set("preferredChannelsText")}
            />
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="persona-decision-criteria">
              Decision criteria (one &quot;factor: value&quot; per line)
            </Label>
            <Textarea
              id="persona-decision-criteria"
              rows={3}
              className="font-mono text-[13px]"
              placeholder={"fees: low\ntrust: high"}
              value={form.decisionCriteriaText}
              onChange={set("decisionCriteriaText")}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="persona-domain">Domain expertise (one &quot;area: level&quot; per line)</Label>
            <Textarea
              id="persona-domain"
              rows={3}
              className="font-mono text-[13px]"
              placeholder={"investing: beginner\nbanking apps: intermediate"}
              value={form.domainText}
              onChange={set("domainText")}
            />
          </div>
        </div>
      </details>

      {error && <p className="text-[13px] text-semantic-warn">{error}</p>}
      <Button type="submit" disabled={isPending} className="self-start">
        {isPending ? "Adding…" : "Add persona"}
      </Button>
    </form>
  );
}
