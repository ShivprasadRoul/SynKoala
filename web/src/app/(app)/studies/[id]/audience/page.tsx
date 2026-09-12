"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { Input, Label, Textarea } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { createAudience, generatePopulation, getAudience } from "@/lib/api/audiences";
import { getStudy } from "@/lib/api/studies";
import type { AudienceDefinition, TraitBand } from "@/lib/types";
import { TRAIT_BANDS } from "@/lib/types";

const TRAIT_BAND_LABELS: Record<TraitBand, string> = {
  low: "Low",
  medium: "Medium",
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

  // --- Define the audience: a statistical population definition, not a persona.
  // Only country/language are required; region/city and age range are optional
  // per the audience-module spec — a researcher may not know either yet. ---
  const [name, setName] = useState("");
  const [country, setCountry] = useState("");
  const [language, setLanguage] = useState("");
  const [city, setCity] = useState("");
  const [ageMin, setAgeMin] = useState("");
  const [ageMax, setAgeMax] = useState("");
  const [confidence, setConfidence] = useState<TraitBand>("medium");
  const [familiarity, setFamiliarity] = useState<TraitBand>("medium");
  const [exploration, setExploration] = useState<TraitBand>("medium");
  const [patience, setPatience] = useState<TraitBand>("medium");
  const [goalDirectedness, setGoalDirectedness] = useState<TraitBand>("medium");
  const [description, setDescription] = useState("");

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
          A distribution of traits — geography, language, and how confident/exploratory this
          group tends to be — that the Audience Engine samples individual participants from.
          This is the population personas are generated from, not a persona itself.
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            createMutation.mutate();
          }}
          className="mt-4 flex flex-col gap-4"
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
              <Label htmlFor="audience-city">Region / city (optional)</Label>
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
        <CardTitle>Generate personas</CardTitle>
        <p className="mt-2 text-[13px] text-ink-muted">
          Samples individual synthetic participants from the audience&apos;s distribution.
          Repeatable — each call adds more participants, it doesn&apos;t replace the existing
          population.
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
        {lastGeneratedCount !== null && (
          <p className="mt-3 font-mono text-[13px] tabular-nums text-ink">
            +{lastGeneratedCount} personas generated this session
          </p>
        )}
      </Card>
    </div>
  );
}
