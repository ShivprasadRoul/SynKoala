"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";

import { SummaryCard } from "@/components/ui/SummaryCard";
import { getAudience } from "@/lib/api/audiences";
import { listStimuli } from "@/lib/api/stimulus";
import { getStudy } from "@/lib/api/studies";
import { listTasks } from "@/lib/api/tasks";
import type { AudienceDefinition, TraitBand } from "@/lib/types";

const TRAIT_LABEL: Record<TraitBand, string> = { low: "Low", medium: "Medium", high: "High" };

// A study's overall lifecycle status (not per-run) is the only simulation
// signal available client-side — there's no endpoint listing a study's runs —
// so this is an honest proxy, not a fabricated count.
const RUN_STARTED_STATUSES = new Set(["RUNNING", "COMPLETED", "FAILED"]);

export default function StudyOverviewPage() {
  const { id } = useParams<{ id: string }>();
  const { data: study } = useQuery({ queryKey: ["study", id], queryFn: () => getStudy(id) });
  const { data: audience } = useQuery({ queryKey: ["audience", id], queryFn: () => getAudience(id) });
  const { data: tasks } = useQuery({ queryKey: ["tasks", id], queryFn: () => listTasks(id) });
  const { data: stimuli } = useQuery({ queryKey: ["stimuli", id], queryFn: () => listStimuli(id) });

  if (!study) return null;

  const definition = audience?.definition as AudienceDefinition | undefined;
  const analyzedScreenCount =
    stimuli?.reduce((sum, s) => sum + s.screens.filter((sc) => sc.elements.length > 0).length, 0) ?? 0;

  const nextStep = !audience
    ? { label: "Define your audience", href: `/studies/${id}/audience` }
    : !tasks?.length
      ? { label: "Define the critical task", href: `/studies/${id}/task` }
      : !analyzedScreenCount
        ? { label: "Import your stimulus", href: `/studies/${id}/stimulus` }
        : { label: "Run a simulation", href: `/studies/${id}/simulation` };

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <SummaryCard
          eyebrow="Audience"
          title={audience ? audience.name : "Not defined yet"}
          status={audience ? "done" : "empty"}
          href={`/studies/${id}/audience`}
          cta={audience ? "View audience" : "Define audience"}
          description={
            audience ? (
              <>
                {[
                  definition?.demographics?.country,
                  definition?.demographics?.city,
                  definition?.demographics?.language,
                ]
                  .filter(Boolean)
                  .join(" · ")}
                {definition?.digital?.familiarity && (
                  <>
                    <br />
                    {TRAIT_LABEL[definition.digital.familiarity]} product familiarity
                  </>
                )}
              </>
            ) : (
              "Define who SynKoala should simulate."
            )
          }
        />

        <SummaryCard
          eyebrow="Task"
          title={tasks?.length ? tasks[0].instruction : "Not defined yet"}
          status={tasks?.length ? "done" : "empty"}
          href={`/studies/${id}/task`}
          cta={tasks?.length ? "View task" : "Define task"}
          description={
            tasks?.length ? "Goal-directed task" : "What should a participant accomplish?"
          }
        />

        <SummaryCard
          eyebrow="Stimulus"
          title={
            stimuli?.length
              ? `${stimuli.length} source${stimuli.length > 1 ? "s" : ""} imported`
              : "Not imported yet"
          }
          status={analyzedScreenCount > 0 ? "done" : stimuli?.length ? "pending" : "empty"}
          href={`/studies/${id}/stimulus`}
          cta={stimuli?.length ? "View stimulus" : "Import stimulus"}
          description={
            stimuli?.length
              ? `${analyzedScreenCount} screen${analyzedScreenCount === 1 ? "" : "s"} analyzed`
              : "Import a Figma prototype or upload a screenshot."
          }
        />

        <SummaryCard
          eyebrow="Simulation"
          title={RUN_STARTED_STATUSES.has(study.status) ? study.status : "Not run yet"}
          status={
            study.status === "COMPLETED"
              ? "done"
              : RUN_STARTED_STATUSES.has(study.status)
                ? "pending"
                : "empty"
          }
          href={`/studies/${id}/simulation`}
          cta="Go to simulation"
          description={`${study.population_size ?? "No"} synthetic users configured`}
        />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-4 rounded-lg bg-ink px-6 py-5 text-canvas shadow-raised">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.06em] text-canvas/60">
            Next step
          </p>
          <p className="mt-1 font-display text-[16px] font-bold">{nextStep.label}</p>
        </div>
        <Link
          href={nextStep.href}
          className="rounded-md bg-primary px-5 py-2.5 text-[14px] font-semibold text-on-primary transition-colors hover:bg-primary-strong"
        >
          Continue setup <span aria-hidden>→</span>
        </Link>
      </div>
    </div>
  );
}
