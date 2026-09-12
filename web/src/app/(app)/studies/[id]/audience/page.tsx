"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { Input, Label, Textarea } from "@/components/ui/Input";
import { createAudience, generatePopulation, getAudience } from "@/lib/api/audiences";

export default function AudiencePage() {
  const { id: studyId } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const { data: audience, isLoading } = useQuery({
    queryKey: ["audience", studyId],
    queryFn: () => getAudience(studyId),
  });

  const [name, setName] = useState("");
  const [definitionJson, setDefinitionJson] = useState(
    '{\n  "demographics": { "age_range": [25, 35], "location": "India" },\n  "digital": { "confidence": "low_medium" }\n}'
  );
  const [definitionError, setDefinitionError] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: () => {
      let definition: object;
      try {
        definition = JSON.parse(definitionJson);
      } catch {
        setDefinitionError("Definition must be valid JSON");
        throw new Error("invalid_json");
      }
      setDefinitionError(null);
      return createAudience(studyId, { name, definition });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["audience", studyId] }),
  });

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

  return (
    <div className="flex flex-col gap-6">
      {!audience ? (
        <Card>
          <CardTitle>Define the audience</CardTitle>
          <p className="mt-2 text-[13px] text-ink-muted">
            A distribution of traits (demographics, digital confidence, behaviour) — the
            Audience Engine samples individual participants from this, it isn&apos;t a fixed
            persona.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              createMutation.mutate();
            }}
            className="mt-4 flex flex-col gap-4"
          >
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="audience-name">Name</Label>
              <Input
                id="audience-name"
                required
                placeholder="First-time banking users"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="definition">Definition (JSON)</Label>
              <Textarea
                id="definition"
                rows={7}
                className="font-mono text-[13px]"
                value={definitionJson}
                onChange={(e) => setDefinitionJson(e.target.value)}
              />
            </div>
            {(definitionError || createMutation.isError) && (
              <p className="text-[13px] text-semantic-warn">
                {definitionError ||
                  (createMutation.error instanceof Error
                    ? createMutation.error.message
                    : "Failed to create audience")}
              </p>
            )}
            <Button type="submit" disabled={createMutation.isPending} className="self-start">
              {createMutation.isPending ? "Creating…" : "Create audience"}
            </Button>
          </form>
        </Card>
      ) : (
        <>
          <Card>
            <CardTitle>{audience.name}</CardTitle>
            <p className="mt-2 text-[13px] text-ink-muted">
              Version {audience.version} · created {new Date(audience.created_at).toLocaleString()}
            </p>
            <pre className="mt-3 overflow-x-auto border border-hairline bg-canvas p-3 font-mono text-[12px] text-ink-muted">
              {JSON.stringify(audience.definition, null, 2)}
            </pre>
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
        </>
      )}
    </div>
  );
}
