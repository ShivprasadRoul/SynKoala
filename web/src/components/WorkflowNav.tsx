"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { getAudience } from "@/lib/api/audiences";
import { listStimuli } from "@/lib/api/stimulus";
import { listTasks } from "@/lib/api/tasks";

const STEPS = [
  { slug: "", label: "Overview" },
  { slug: "audience", label: "Audience" },
  { slug: "task", label: "Task" },
  { slug: "stimulus", label: "Stimulus" },
  { slug: "simulation", label: "Simulation" },
] as const;

// The study workflow as a stepper, not a plain tab bar — each step shows a
// checkmark once it's genuinely satisfied (an audience exists, a task exists,
// at least one stimulus screen has been analyzed), computed from the same
// queries the individual tabs already run, so this reflects real state rather
// than a client-side flag. There's no endpoint to list a study's simulation
// runs, so "Simulation" never gets a checkmark here — it's always the
// destination, matching how far the workflow can honestly be tracked.
export function WorkflowNav({ studyId }: { studyId: string }) {
  const pathname = usePathname();
  const base = `/studies/${studyId}`;

  const { data: audience } = useQuery({
    queryKey: ["audience", studyId],
    queryFn: () => getAudience(studyId),
  });
  const { data: tasks } = useQuery({ queryKey: ["tasks", studyId], queryFn: () => listTasks(studyId) });
  const { data: stimuli } = useQuery({
    queryKey: ["stimuli", studyId],
    queryFn: () => listStimuli(studyId),
  });

  const completed: Record<string, boolean> = {
    audience: Boolean(audience),
    task: Boolean(tasks && tasks.length > 0),
    stimulus: Boolean(stimuli?.some((s) => s.screens.some((screen) => screen.elements.length > 0))),
  };

  return (
    <nav className="flex gap-1 overflow-x-auto">
      {STEPS.map((step, index) => {
        const href = step.slug ? `${base}/${step.slug}` : base;
        const isActive = pathname === href;
        const isDone = completed[step.slug];
        return (
          <Link
            key={step.slug}
            href={href}
            aria-current={isActive ? "page" : undefined}
            className={`flex shrink-0 items-center gap-2 rounded-md px-3 py-2 text-[13px] font-medium transition-colors ${
              isActive ? "bg-ink text-canvas" : "text-ink-muted hover:bg-surface-1 hover:text-ink"
            }`}
          >
            {isDone ? (
              <span
                className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${
                  isActive ? "bg-primary text-on-primary" : "bg-primary-soft text-primary-deep"
                }`}
                aria-hidden
              >
                ✓
              </span>
            ) : (
              <span
                className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-full font-mono text-[10px] ${
                  isActive ? "bg-canvas/25 text-canvas" : "bg-surface-2 text-ink-tertiary"
                }`}
                aria-hidden
              >
                {String(index + 1).padStart(2, "0")}
              </span>
            )}
            {step.label}
          </Link>
        );
      })}
    </nav>
  );
}
