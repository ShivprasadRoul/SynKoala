"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";

import { StudyTabs } from "@/components/StudyTabs";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { getStudy } from "@/lib/api/studies";

export default function StudyLayout({ children }: { children: React.ReactNode }) {
  const { id } = useParams<{ id: string }>();
  const { data: study, isLoading } = useQuery({
    queryKey: ["study", id],
    queryFn: () => getStudy(id),
  });

  if (isLoading || !study) {
    return <p className="text-[14px] text-ink-muted">Loading study…</p>;
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-[24px] font-extrabold tracking-[-0.3px] text-ink">
            {study.name}
          </h1>
          {study.objective && <p className="mt-1 text-[14px] text-ink-muted">{study.objective}</p>}
        </div>
        <StatusBadge status={study.status} />
      </div>
      <StudyTabs studyId={id} />
      <div>{children}</div>
    </div>
  );
}
