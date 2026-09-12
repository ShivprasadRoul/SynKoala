"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { Card } from "@/components/ui/Card";
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
        <h1 className="font-display text-[26px] font-extrabold tracking-[-0.4px] text-ink">
          Studies
        </h1>
        <Link
          href="/studies/new"
          className="bg-primary px-5 py-2.5 text-[14px] font-semibold text-on-primary hover:bg-primary-strong"
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
        <Card>
          <p className="text-[14px] text-ink-muted">
            No studies yet. Create one to define an audience, a task, and a stimulus to test.
          </p>
        </Card>
      )}

      <div className="flex flex-col gap-3">
        {studies?.map((study) => (
          <Link key={study.id} href={`/studies/${study.id}`}>
            <Card className="flex items-center justify-between transition-colors hover:border-hairline-strong">
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
