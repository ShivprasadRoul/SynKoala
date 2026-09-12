"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { listStudies } from "@/lib/api/studies";

export default function DashboardPage() {
  const { data: studies, isLoading, error } = useQuery({
    queryKey: ["studies"],
    queryFn: listStudies,
  });

  return (
    <div className="flex flex-col gap-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-[26px] font-extrabold tracking-[-0.4px] text-ink">
            Studies
          </h1>
          <p className="mt-1 text-[13px] text-ink-muted">
            Your synthetic user-research workspace.
          </p>
        </div>
        <Link
          href="/studies/new"
          className="rounded-md bg-primary px-5 py-2.5 text-[14px] font-semibold text-on-primary shadow-sm transition-colors hover:bg-primary-strong"
        >
          New study
        </Link>
      </div>

      {isLoading && <p className="text-[14px] text-ink-muted">Loading studies…</p>}
      {error && (
        <p className="text-[14px] text-semantic-warn">
          {error instanceof Error ? error.message : "Failed to load studies"}
        </p>
      )}

      {studies && studies.length === 0 && (
        <EmptyState
          title="No studies yet"
          description="Create one to define an audience, a task, and a stimulus to test with synthetic users."
        />
      )}

      <div className="flex flex-col gap-3">
        {studies?.map((study) => (
          <Link key={study.id} href={`/studies/${study.id}`}>
            <Card className="flex items-center justify-between transition-shadow hover:shadow-raised">
              <div>
                <h2 className="font-display text-[16px] font-bold text-ink">{study.name}</h2>
                {study.objective && (
                  <p className="mt-1 text-[13px] text-ink-muted">{study.objective}</p>
                )}
              </div>
              <StatusBadge status={study.status} />
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
