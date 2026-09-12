"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Input, Label, Textarea } from "@/components/ui/Input";
import { createStudy } from "@/lib/api/studies";

export default function NewStudyPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [objective, setObjective] = useState("");
  const [populationSize, setPopulationSize] = useState(50);

  const mutation = useMutation({
    mutationFn: () =>
      createStudy({ name, objective: objective || null, population_size: populationSize }),
    onSuccess: (study) => router.push(`/studies/${study.id}`),
  });

  return (
    <div className="max-w-[560px]">
      <h1 className="font-display text-[24px] font-extrabold tracking-[-0.3px] text-ink">
        New study
      </h1>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          mutation.mutate();
        }}
        className="mt-8 flex flex-col gap-4"
      >
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="name">Name</Label>
          <Input
            id="name"
            required
            placeholder="Banking app usability"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="objective">Objective (optional)</Label>
          <Textarea
            id="objective"
            rows={3}
            placeholder="Can first-time users transfer money?"
            value={objective}
            onChange={(e) => setObjective(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="population-size">Sample size</Label>
          <Input
            id="population-size"
            type="number"
            min={1}
            max={1000}
            value={populationSize}
            onChange={(e) => setPopulationSize(Number(e.target.value))}
          />
          <p className="text-[12px] text-ink-tertiary">
            Default population for this study&apos;s runs — used when generating the audience
            and when a run is started without its own size, e.g. auto-started from the mobile
            app after a defined-path walkthrough.
          </p>
        </div>
        {mutation.isError && (
          <p className="text-[13px] text-semantic-warn">
            {mutation.error instanceof Error ? mutation.error.message : "Failed to create study"}
          </p>
        )}
        <Button type="submit" disabled={mutation.isPending} className="mt-2 self-start">
          {mutation.isPending ? "Creating…" : "Create study"}
        </Button>
      </form>
    </div>
  );
}
