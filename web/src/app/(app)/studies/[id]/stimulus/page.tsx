"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { Input, Label } from "@/components/ui/Input";
import { listStimuli, uploadStimulus } from "@/lib/api/stimulus";

export default function StimulusPage() {
  const { id: studyId } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const { data: stimuli, isLoading } = useQuery({
    queryKey: ["stimuli", studyId],
    queryFn: () => listStimuli(studyId),
  });

  const [type, setType] = useState("mobile_ui");
  const [file, setFile] = useState<File | null>(null);
  const [sourceUrl, setSourceUrl] = useState("");

  const uploadMutation = useMutation({
    mutationFn: () => uploadStimulus(studyId, { type, file, sourceUrl: sourceUrl || null }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["stimuli", studyId] });
      setFile(null);
      setSourceUrl("");
    },
  });

  if (isLoading) return <p className="text-[14px] text-ink-muted">Loading stimuli…</p>;

  return (
    <div className="flex flex-col gap-6">
      {stimuli && stimuli.length > 0 && (
        <div className="flex flex-col gap-3">
          {stimuli.map((stimulus) => (
            <Card key={stimulus.id} className="flex items-center justify-between">
              <div>
                <p className="text-[14px] font-semibold text-ink">{stimulus.type}</p>
                <p className="text-[12px] text-ink-tertiary">
                  {stimulus.screens.length} screen(s) · v{stimulus.version}
                </p>
              </div>
              {stimulus.source_url && (
                <span className="text-[12px] text-ink-muted">{stimulus.source_url}</span>
              )}
            </Card>
          ))}
        </div>
      )}

      <Card>
        <CardTitle>Upload a stimulus</CardTitle>
        <p className="mt-2 text-[13px] text-ink-muted">
          A screenshot, prototype flow, or a Figma-linked reference for participants to
          interact with.
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            uploadMutation.mutate();
          }}
          className="mt-4 flex flex-col gap-4"
        >
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="type">Type</Label>
            <Input id="type" value={type} onChange={(e) => setType(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="file">Image file (optional)</Label>
            <input
              id="file"
              type="file"
              accept="image/*"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="text-[13px] text-ink-muted"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="source-url">Source URL (optional)</Label>
            <Input
              id="source-url"
              placeholder="https://figma.com/..."
              value={sourceUrl}
              onChange={(e) => setSourceUrl(e.target.value)}
            />
          </div>
          {uploadMutation.isError && (
            <p className="text-[13px] text-semantic-warn">
              {uploadMutation.error instanceof Error
                ? uploadMutation.error.message
                : "Failed to upload stimulus"}
            </p>
          )}
          <Button type="submit" disabled={uploadMutation.isPending} className="self-start">
            {uploadMutation.isPending ? "Uploading…" : "Upload"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
