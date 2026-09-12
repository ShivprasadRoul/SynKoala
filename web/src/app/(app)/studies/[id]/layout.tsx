"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";

import { StudyHeader } from "@/components/StudyHeader";
import { WorkflowNav } from "@/components/WorkflowNav";
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
    <div className="flex flex-col gap-8">
      <StudyHeader study={study} />
      <div className="border-b border-hairline">
        <WorkflowNav studyId={id} />
      </div>
      <div>{children}</div>
    </div>
  );
}
