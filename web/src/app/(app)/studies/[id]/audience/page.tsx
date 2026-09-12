"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useState } from "react";

import { PersonaCard } from "@/components/audience/PersonaCard";
import { PersonaForm } from "@/components/audience/PersonaForm";
import { Button } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { Input, Label, Textarea } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { addPersona, createAudience, generatePopulation, getAudience } from "@/lib/api/audiences";
import type { AudienceDefinition, Persona, TraitBand } from "@/lib/types";
import { TRAIT_BANDS } from "@/lib/types";

const TRAIT_BAND_LABELS: Record<TraitBand, string> = {
  low: "Low",
  low_medium: "Low-medium",
  medium: "Medium",
  medium_high: "Medium-high",
  high: "High",
};

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

export default function AudiencePage() {
  const { id: studyId } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const { data: audience, isLoading } = useQuery({
    queryKey: ["audience", studyId],
    queryFn: () => getAudience(studyId),
  });

  // --- Step 1: define the audience group (country/age/city/trait distribution) ---
  const [name, setName] = useState("");
  const [country, setCountry] = useState("India");
  const [language, setLanguage] = useState("English");
  const [city, setCity] = useState("");
  const [ageMin, setAgeMin] = useState(25);
  const [ageMax, setAgeMax] = useState(35);
  const [confidence, setConfidence] = useState<TraitBand>("medium");
  const [familiarity, setFamiliarity] = useState<TraitBand>("medium");
  const [exploration, setExploration] = useState<TraitBand>("medium");
  const [patience, setPatience] = useState<TraitBand>("medium");
  const [goalDirectedness, setGoalDirectedness] = useState<TraitBand>("medium");
  const [description, setDescription] = useState("");

  const createMutation = useMutation({
    mutationFn: () => {
      const definition: AudienceDefinition = {
        demographics: {
          country,
          language,
          city: city || undefined,
          age_range: [ageMin, ageMax],
        },
        digital: { confidence, familiarity },
        behaviour: { exploration, patience, goal_directedness: goalDirectedness },
        description: description || undefined,
        personas: [],
      };
      return createAudience(studyId, { name, definition });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["audience", studyId] }),
  });

  // --- Step 2: add one or more target personas within that audience ---
  const [showPersonaForm, setShowPersonaForm] = useState(false);
  const addPersonaMutation = useMutation({
    mutationFn: (persona: Persona) => addPersona(studyId, persona),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["audience", studyId] });
      setShowPersonaForm(false);
    },
  });

  // --- Step 3: sample a synthetic population from the audience's distribution ---
  const [populationSize, setPopulationSize] = useState(50);
  const [seed, setSeed] = useState<string>("");
  const [lastGeneratedCount, setLastGeneratedCount] = useState<number | null>(null);

  const generateMutation = useMutation({
    mutationFn: () =>
      generatePopulation(studyId, {
        population_size: populationSize,
        seed: seed ? Number(seed) : null,
      }),
    onSuccess: (participants) => setLastGeneratedCount(participants.length),
  });

  if (isLoading) return <p className="text-[14px] text-ink-muted">Loading audience…</p>;

  if (!audience) {
    return (
      <Card>
        <CardTitle>Define the audience</CardTitle>
        <p className="mt-2 text-[13px] text-ink-muted">
          A distribution of traits — country, age, and how confident/exploratory this group
          tends to be — that the Audience Engine samples individual participants from. This
          isn&apos;t a fixed persona; it&apos;s the population the personas below are drawn
          from.
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            createMutation.mutate();
          }}
          className="mt-4 flex flex-col gap-4"
        >
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="audience-name">Audience group name</Label>
            <Input
              id="audience-name"
              required
              placeholder="First-time banking users"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

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
              <Label htmlFor="audience-city">City (optional)</Label>
              <Input
                id="audience-city"
                placeholder="Mumbai"
                value={city}
                onChange={(e) => setCity(e.target.value)}
              />
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="audience-age-min">Age range</Label>
            <div className="flex items-center gap-3">
              <Input
                id="audience-age-min"
                type="number"
                min={13}
                max={99}
                className="w-24"
                value={ageMin}
                onChange={(e) => setAgeMin(Number(e.target.value))}
              />
              <span className="text-[13px] text-ink-tertiary">to</span>
              <Input
                type="number"
                min={13}
                max={99}
                className="w-24"
                value={ageMax}
                onChange={(e) => setAgeMax(Number(e.target.value))}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <TraitBandSelect
              id="audience-confidence"
              label="Digital confidence"
              value={confidence}
              onChange={setConfidence}
            />
            <TraitBandSelect
              id="audience-familiarity"
              label="Product familiarity"
              value={familiarity}
              onChange={setFamiliarity}
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

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="audience-description">Description (optional)</Label>
            <Textarea
              id="audience-description"
              rows={2}
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
  const personas = definition.personas ?? [];

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardTitle>{audience.name}</CardTitle>
        <p className="mt-2 text-[13px] text-ink-muted">
          {definition.demographics?.country}
          {definition.demographics?.city ? ` · ${definition.demographics.city}` : ""}
          {definition.demographics?.age_range
            ? ` · Ages ${definition.demographics.age_range[0]}-${definition.demographics.age_range[1]}`
            : ""}
          {definition.demographics?.language ? ` · ${definition.demographics.language}` : ""}
        </p>
        <p className="mt-1 text-[13px] text-ink-tertiary">
          Version {audience.version} · created {new Date(audience.created_at).toLocaleString()}
        </p>
        <details className="mt-3">
          <summary className="cursor-pointer text-[13px] text-ink-subtle">
            View raw definition
          </summary>
          <pre className="mt-2 overflow-x-auto border border-hairline bg-canvas p-3 font-mono text-[12px] text-ink-muted">
            {JSON.stringify(audience.definition, null, 2)}
          </pre>
        </details>
      </Card>

      <Card>
        <div className="flex items-center justify-between">
          <CardTitle>Target personas</CardTitle>
          {!showPersonaForm && (
            <Button variant="secondary" onClick={() => setShowPersonaForm(true)}>
              + Add persona
            </Button>
          )}
        </div>
        <p className="mt-2 text-[13px] text-ink-muted">
          Qualitative profiles the synthetic population should represent — descriptive colour
          for the study, not the statistical distribution itself.
        </p>

        {personas.length > 0 && (
          <div className="mt-4 flex flex-col gap-3">
            {personas.map((persona, index) => (
              <PersonaCard key={`${persona.persona_name}-${index}`} persona={persona} />
            ))}
          </div>
        )}

        {showPersonaForm && (
          <div className="mt-4 border-t border-hairline pt-4">
            <PersonaForm
              defaultCountry={definition.demographics?.country}
              defaultLanguage={definition.demographics?.language}
              onSubmit={(persona) => addPersonaMutation.mutate(persona)}
              isPending={addPersonaMutation.isPending}
              error={
                addPersonaMutation.isError
                  ? addPersonaMutation.error instanceof Error
                    ? addPersonaMutation.error.message
                    : "Failed to add persona"
                  : null
              }
            />
          </div>
        )}
      </Card>

      <Card>
        <CardTitle>Generate population</CardTitle>
        <p className="mt-2 text-[13px] text-ink-muted">
          Samples participants from the audience&apos;s distribution. Repeatable — each call
          adds more participants, it doesn&apos;t replace the existing population.
        </p>
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
              onChange={(e) => setPopulationSize(Number(e.target.value))}
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
          <Button type="submit" variant="secondary" disabled={generateMutation.isPending}>
            {generateMutation.isPending ? "Generating…" : "Generate"}
          </Button>
        </form>
        {generateMutation.isError && (
          <p className="mt-3 text-[13px] text-semantic-warn">
            {generateMutation.error instanceof Error
              ? generateMutation.error.message
              : "Failed to generate population"}
          </p>
        )}
        {lastGeneratedCount !== null && (
          <p className="mt-3 font-mono text-[13px] tabular-nums text-ink">
            +{lastGeneratedCount} participants generated this session
          </p>
        )}
      </Card>
    </div>
  );
}
