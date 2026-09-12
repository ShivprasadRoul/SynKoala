"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { getAudience } from "@/lib/api/audiences";
import { getStudy, updateStudy } from "@/lib/api/studies";

export default function StudyOverviewPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const { data: study } = useQuery({ queryKey: ["study", id], queryFn: () => getStudy(id) });
  const { data: audience } = useQuery({ queryKey: ["audience", id], queryFn: () => getAudience(id) });

  const markReady = useMutation({
    mutationFn: () => updateStudy(id, { status: "READY" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["study", id] }),
  });

  if (!study) return null;

  const canPublish = Boolean(audience);

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <h2 className="font-display text-[16px] font-bold text-ink">Study lifecycle</h2>
        <p className="mt-2 text-[13px] text-ink-muted">
          DRAFT → READY → RUNNING → COMPLETED/FAILED. A simulation can only be started once the
          study is READY — set up an audience, task, and stimulus first.
        </p>
        {study.status === "DRAFT" && (
          <>
            <Button
              variant="secondary"
              className="mt-4"
              disabled={markReady.isPending || !canPublish}
              onClick={() => markReady.mutate()}
            >
              {markReady.isPending ? "Marking ready…" : "Mark study READY"}
            </Button>
            {!canPublish && (
              <p className="mt-2 text-[13px] text-ink-muted">
                Add an audience segment before publishing this study.
              </p>
            )}
          </>
        )}
        {markReady.isError && (
          <p className="mt-3 text-[13px] text-semantic-warn">
            {markReady.error instanceof Error
              ? markReady.error.message
              : "Couldn't update the study"}
          </p>
        )}
      </Card>
    </div>
  );
}
