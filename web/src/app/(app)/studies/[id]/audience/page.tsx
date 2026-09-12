"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useState } from "react";

import { PersonaCard } from "@/components/persona/PersonaCard";
import { PersonaDetailModal } from "@/components/persona/PersonaDetailModal";
import { Button } from "@/components/ui/Button";
import { Card, CardDescription, CardTitle } from "@/components/ui/Card";
import { HelperText, Input, Label, Textarea } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import {
  createAudience,
  generatePopulation,
  getAudience,
  listParticipants,
} from "@/lib/api/audiences";
import { getStudy } from "@/lib/api/studies";
import type { AudienceDefinition, GeneratedPersona, Participant, TraitBand } from "@/lib/types";
import { TRAIT_BANDS } from "@/lib/types";

const TRAIT_BAND_LABELS: Record<TraitBand, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
};

// A researcher usually knows who their audience *is* ("marketing professionals",
// "people in rural areas") long before they'd know how to score them on abstract
// bands like "exploration" or "patience". Each preset supplies sensible defaults
// for the three hardest-to-judge traits; the exact bands stay editable under
// "Advanced" for anyone who wants to override them.
const AUDIENCE_CONTEXT_PRESETS = [
  {
    id: "general",
    label: "General / not sure yet",
    confidence: "medium",
    exploration: "medium",
    patience: "medium",
  },
  {
    id: "rural_first_time",
    label: "Rural or first-time internet users",
    confidence: "low",
    exploration: "low",
    patience: "low",
  },
  {
    id: "urban_professional",
    label: "Urban working professionals",
    confidence: "high",
    exploration: "medium",
    patience: "medium",
  },
  {
    id: "marketing_growth",
    label: "Marketing / growth / performance-driven users",
    confidence: "high",
    exploration: "high",
    patience: "low",
  },
  {
    id: "students_young_adults",
    label: "Students or young adults",
    confidence: "medium",
    exploration: "high",
    patience: "medium",
  },
  {
    id: "senior_less_tech_savvy",
    label: "Senior citizens / less tech-savvy users",
    confidence: "low",
    exploration: "low",
    patience: "high",
  },
] as const satisfies ReadonlyArray<{
  id: string;
  label: string;
  confidence: TraitBand;
  exploration: TraitBand;
  patience: TraitBand;
}>;

function TraitBandSelect({
  id,
  label,
  value,
  onChange,
}: {
  id: string;
  label: string;
  value: TraitBand;
  onChange: (value: TraitBand) => void;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Select id={id} value={value} onChange={(e) => onChange(e.target.value as TraitBand)}>
        {TRAIT_BANDS.map((band) => (
          <option key={band} value={band}>
            {TRAIT_BAND_LABELS[band]}
          </option>
        ))}
      </Select>
    </div>
  );
}

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-tertiary">
      {children}
    </h3>
  );
}

export default function AudiencePage() {
  const { id: studyId } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const { data: audience, isLoading } = useQuery({
    queryKey: ["audience", studyId],
    queryFn: () => getAudience(studyId),
  });

  // --- Define the audience: a statistical population definition, not a persona.
  // Only country/language are required; region/city and age range are optional
  // per the audience-module spec — a researcher may not know either yet. ---
  const [name, setName] = useState("");
  const [country, setCountry] = useState("");
  const [language, setLanguage] = useState("");
  const [city, setCity] = useState("");
  const [ageMin, setAgeMin] = useState("");
  const [ageMax, setAgeMax] = useState("");
  const [contextPreset, setContextPreset] = useState<string>(AUDIENCE_CONTEXT_PRESETS[0].id);
  const [confidence, setConfidence] = useState<TraitBand>("medium");
  const [familiarity, setFamiliarity] = useState<TraitBand>("medium");
  const [exploration, setExploration] = useState<TraitBand>("medium");
  const [patience, setPatience] = useState<TraitBand>("medium");
  const [goalDirectedness, setGoalDirectedness] = useState<TraitBand>("medium");
  const [description, setDescription] = useState("");

  function applyContextPreset(presetId: string) {
    setContextPreset(presetId);
    const preset = AUDIENCE_CONTEXT_PRESETS.find((p) => p.id === presetId);
    if (!preset) return;
    setConfidence(preset.confidence);
    setExploration(preset.exploration);
    setPatience(preset.patience);
  }

  const createMutation = useMutation({
    mutationFn: () => {
      const min = ageMin.trim() ? Number(ageMin) : undefined;
      const max = ageMax.trim() ? Number(ageMax) : undefined;
      const definition: AudienceDefinition = {
        demographics: {
          country,
          language,
          city: city.trim() || undefined,
          age_range: min !== undefined && max !== undefined ? [min, max] : undefined,
        },
        digital: { confidence, familiarity },
        behaviour: { exploration, patience, goal_directedness: goalDirectedness },
        description: description.trim() || undefined,
      };
      return createAudience(studyId, { name, definition });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["audience", studyId] }),
  });

  // --- Generate personas: samples individual participants from the audience's
  // statistical prior (AudienceEngine.sample_participants) — the audience itself
  // stays a distribution, never a fixed persona. Defaults to the study's own
  // sample size (set at creation) rather than a hardcoded number — the same
  // default the mobile app uses when it auto-starts a run after a defined-path
  // walkthrough. ---
  const { data: study } = useQuery({ queryKey: ["study", studyId], queryFn: () => getStudy(studyId) });
  const [populationSizeOverride, setPopulationSizeOverride] = useState<number | null>(null);
  const populationSize = populationSizeOverride ?? study?.population_size ?? 50;
  const [seed, setSeed] = useState<string>("");
  const [viewingPersona, setViewingPersona] = useState<GeneratedPersona | null>(null);

  // Every participant generated so far, persisted server-side — fetched on
  // every visit (not just held from the last `generate` response) so a page
  // refresh still shows what was generated minutes or days ago.
  const { data: participants } = useQuery({
    queryKey: ["participants", studyId],
    queryFn: () => listParticipants(studyId),
    enabled: Boolean(audience),
  });

  const generateMutation = useMutation({
    mutationFn: () =>
      generatePopulation(studyId, {
        population_size: populationSize,
        seed: seed ? Number(seed) : null,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["participants", studyId] }),
  });

  if (isLoading) return <p className="text-[14px] text-ink-muted">Loading audience…</p>;

  if (!audience) {
    return (
      <Card className="max-w-[720px]">
        <CardTitle>Define the audience</CardTitle>
        <CardDescription className="mt-2">
          A distribution of traits — geography, language, and how confident/exploratory this
          group tends to be — that the Audience Engine samples individual participants from.
          This is the population personas are generated from, not a persona itself.
        </CardDescription>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            createMutation.mutate();
          }}
          className="mt-6 flex flex-col gap-6"
        >
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="audience-name">Audience name</Label>
            <Input
              id="audience-name"
              required
              placeholder="First-time banking users"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          <div className="flex flex-col gap-3 border-t border-hairline pt-5">
            <SectionHeading>Location &amp; language</SectionHeading>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="audience-country">Country</Label>
                <Input
                  id="audience-country"
                  required
                  value={country}
                  onChange={(e) => setCountry(e.target.value)}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="audience-language">Language</Label>
                <Input
                  id="audience-language"
                  required
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="audience-city">Region (optional)</Label>
                <Input
                  id="audience-city"
                  placeholder="Mumbai"
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                />
              </div>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="audience-age-min">Age range (optional)</Label>
              <div className="flex items-center gap-3">
                <Input
                  id="audience-age-min"
                  type="number"
                  min={13}
                  max={99}
                  placeholder="Min"
                  className="w-24"
                  value={ageMin}
                  onChange={(e) => setAgeMin(e.target.value)}
                />
                <span className="text-[13px] text-ink-tertiary">to</span>
                <Input
                  type="number"
                  min={13}
                  max={99}
                  placeholder="Max"
                  className="w-24"
                  value={ageMax}
                  onChange={(e) => setAgeMax(e.target.value)}
                />
              </div>
            </div>
          </div>

          <div className="flex flex-col gap-3 border-t border-hairline pt-5">
            <SectionHeading>User characteristics</SectionHeading>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="audience-context-preset">Who is this audience?</Label>
                <Select
                  id="audience-context-preset"
                  value={contextPreset}
                  onChange={(e) => applyContextPreset(e.target.value)}
                >
                  {AUDIENCE_CONTEXT_PRESETS.map((preset) => (
                    <option key={preset.id} value={preset.id}>
                      {preset.label}
                    </option>
                  ))}
                </Select>
              </div>
              <TraitBandSelect
                id="audience-familiarity"
                label="Product familiarity"
                value={familiarity}
                onChange={setFamiliarity}
              />
            </div>
            <HelperText>
              The preset sets sensible defaults for digital confidence, exploration, and patience
              — fine-tune the exact bands under Advanced if you need to.
            </HelperText>

            <details className="group mt-1 rounded-md border border-hairline bg-surface-1/50 p-4">
              <summary className="cursor-pointer text-[13px] font-semibold text-ink-subtle">
                Advanced: fine-tune behavioral traits
              </summary>
              <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
                <TraitBandSelect
                  id="audience-confidence"
                  label="Digital confidence"
                  value={confidence}
                  onChange={setConfidence}
                />
                <TraitBandSelect
                  id="audience-exploration"
                  label="Exploration"
                  value={exploration}
                  onChange={setExploration}
                />
                <TraitBandSelect
                  id="audience-patience"
                  label="Patience"
                  value={patience}
                  onChange={setPatience}
                />
                <TraitBandSelect
                  id="audience-goal-directedness"
                  label="Goal-directedness"
                  value={goalDirectedness}
                  onChange={setGoalDirectedness}
                />
              </div>
            </details>
          </div>

          <div className="flex flex-col gap-1.5 border-t border-hairline pt-5">
            <Label htmlFor="audience-description">Description (optional)</Label>
            <Textarea
              id="audience-description"
              rows={2}
              placeholder="Free-form notes for context — not used as a sampling input."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          {createMutation.isError && (
            <p className="text-[13px] text-semantic-warn">
              {createMutation.error instanceof Error
                ? createMutation.error.message
                : "Failed to create audience"}
            </p>
          )}
          <Button type="submit" disabled={createMutation.isPending} className="self-start">
            {createMutation.isPending ? "Creating…" : "Create audience"}
          </Button>
        </form>
      </Card>
    );
  }

  const definition = audience.definition as AudienceDefinition;

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <div className="flex items-center gap-2">
          <span className="h-1.5 w-1.5 rounded-full bg-primary" />
          <span className="text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-tertiary">
            Audience
          </span>
        </div>
        <CardTitle className="mt-1.5">{audience.name}</CardTitle>
        <p className="mt-2 text-[13px] text-ink-muted">
          {[
            definition.demographics?.country,
            definition.demographics?.city,
            definition.demographics?.language,
          ]
            .filter(Boolean)
            .join(" · ")}
          {definition.demographics?.age_range
            ? ` · Ages ${definition.demographics.age_range[0]}-${definition.demographics.age_range[1]}`
            : ""}
        </p>
        <p className="mt-1 text-[12px] text-ink-tertiary">
          Version {audience.version} · created {new Date(audience.created_at).toLocaleString()}
        </p>
        <details className="mt-3">
          <summary className="cursor-pointer text-[13px] text-ink-subtle">
            View raw definition
          </summary>
          <pre className="mt-2 overflow-x-auto rounded-md border border-hairline bg-canvas p-3 font-mono text-[12px] text-ink-muted">
            {JSON.stringify(audience.definition, null, 2)}
          </pre>
        </details>
      </Card>

      <div className="flex justify-center text-ink-tertiary" aria-hidden>
        ↓
      </div>

      <Card>
        <div className="flex items-center gap-2">
          <span className="h-1.5 w-1.5 rounded-full bg-primary" />
          <span className="text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-tertiary">
            Generated synthetic users
          </span>
        </div>
        <CardTitle className="mt-1.5">Synthetic users</CardTitle>
        <CardDescription className="mt-1">
          SynKoala generates individual users from your audience — each one an independent sample
          from its distribution, not a copy of it. Repeatable — each call adds more, it
          doesn&apos;t replace the existing population.
        </CardDescription>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            generateMutation.mutate();
          }}
          className="mt-4 flex flex-wrap items-end gap-4"
        >
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="population-size">Population size</Label>
            <Input
              id="population-size"
              type="number"
              min={1}
              max={1000}
              className="w-32"
              value={populationSize}
              onChange={(e) => setPopulationSizeOverride(Number(e.target.value))}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="seed">Seed (optional)</Label>
            <Input
              id="seed"
              type="number"
              className="w-32"
              value={seed}
              onChange={(e) => setSeed(e.target.value)}
            />
          </div>
          <Button type="submit" disabled={generateMutation.isPending}>
            {generateMutation.isPending ? "Generating…" : "Generate Personas"}
          </Button>
        </form>
        {generateMutation.isError && (
          <p className="mt-3 text-[13px] text-semantic-warn">
            {generateMutation.error instanceof Error
              ? generateMutation.error.message
              : "Failed to generate personas"}
          </p>
        )}
        {participants && participants.length > 0 && (
          <div className="mt-5 border-t border-hairline pt-4">
            <p className="font-mono text-[13px] tabular-nums text-ink">
              {participants.length} synthetic user{participants.length === 1 ? "" : "s"} generated
              so far
            </p>
            <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {participants
                .filter((participant): participant is Participant & { persona: GeneratedPersona } =>
                  Boolean(participant.persona)
                )
                .slice(0, 9)
                .map((participant) => (
                  <PersonaCard
                    key={participant.id}
                    persona={participant.persona}
                    onView={() => setViewingPersona(participant.persona)}
                  />
                ))}
            </div>
            {participants.length > 9 && (
              <p className="mt-2 text-[12px] text-ink-tertiary">
                +{participants.length - 9} more not shown
              </p>
            )}
          </div>
        )}
      </Card>

      {viewingPersona && (
        <PersonaDetailModal persona={viewingPersona} onClose={() => setViewingPersona(null)} />
      )}
    </div>
  );
}
