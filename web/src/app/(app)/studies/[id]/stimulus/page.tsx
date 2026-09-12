"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useState } from "react";

import { getFigmaAuthorizeUrl } from "@/lib/api/auth";
import { analyzeStimuli, listStimuli, uploadStimulus } from "@/lib/api/stimulus";

import { Button } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { Input, Label } from "@/components/ui/Input";

export default function StimulusPage() {
  const { id: studyId } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const { data: stimuli, isLoading } = useQuery({
    queryKey: ["stimuli", studyId],
    queryFn: () => listStimuli(studyId),
  });

  // --- Import from Figma: fetches the file via the connected account's OAuth
  // token and persists real screens/elements/transitions directly, no vision
  // model needed (planning/05-stimulus-engine.md's Figma import path). ---
  const [figmaUrl, setFigmaUrl] = useState("");

  const importFigmaMutation = useMutation({
    mutationFn: async () => {
      await uploadStimulus(studyId, { type: "figma", sourceUrl: figmaUrl });
      return analyzeStimuli(studyId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["stimuli", studyId] });
      setFigmaUrl("");
    },
  });

  const connectFigmaMutation = useMutation({
    mutationFn: getFigmaAuthorizeUrl,
    onSuccess: (url) => {
      window.location.href = url;
    },
  });

  // --- Upload a screenshot: analysis is a separate, explicit step so several
  // screenshots can be uploaded first and analyzed together in one job batch. ---
  const [type, setType] = useState("mobile_ui");
  const [file, setFile] = useState<File | null>(null);

  const uploadMutation = useMutation({
    mutationFn: () => uploadStimulus(studyId, { type, file, sourceUrl: null }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["stimuli", studyId] });
      setFile(null);
    },
  });

  const analyzeMutation = useMutation({
    mutationFn: () => analyzeStimuli(studyId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["stimuli", studyId] }),
  });

  if (isLoading) return <p className="text-[14px] text-ink-muted">Loading stimuli…</p>;

  const hasUnanalyzedScreenshot = (stimuli ?? []).some(
    (s) => s.type !== "figma" && s.screens.every((screen) => screen.elements.length === 0)
  );

  return (
    <div className="flex flex-col gap-6">
      {stimuli && stimuli.length > 0 && (
        <div className="flex flex-col gap-3">
          {stimuli.map((stimulus) => {
            const analyzedScreens = stimulus.screens.filter((s) => s.elements.length > 0).length;
            return (
              <Card key={stimulus.id} className="flex items-center justify-between">
                <div>
                  <p className="text-[14px] font-semibold text-ink">{stimulus.type}</p>
                  <p className="text-[12px] text-ink-tertiary">
                    {stimulus.screens.length} screen(s), {analyzedScreens} analyzed · v
                    {stimulus.version}
                  </p>
                </div>
                {stimulus.source_url && (
                  <span className="max-w-[320px] truncate text-[12px] text-ink-muted">
                    {stimulus.source_url}
                  </span>
                )}
              </Card>
            );
          })}
        </div>
      )}

      <Card>
        <div className="flex items-center justify-between">
          <CardTitle>Import from Figma</CardTitle>
          <button
            type="button"
            onClick={() => connectFigmaMutation.mutate()}
            className="text-[13px] font-semibold text-ink-muted hover:text-ink"
          >
            {connectFigmaMutation.isPending ? "Redirecting…" : "Connect Figma account"}
          </button>
        </div>
        <p className="mt-2 text-[13px] text-ink-muted">
          Fetches every frame in the file directly from Figma — real bounding boxes and
          navigation links, no screenshot needed. The file must be viewable by the connected
          Figma account (owned, shared, or &quot;anyone with the link&quot;).
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            importFigmaMutation.mutate();
          }}
          className="mt-4 flex flex-wrap items-end gap-4"
        >
          <div className="flex flex-1 flex-col gap-1.5">
            <Label htmlFor="figma-url">Figma prototype URL</Label>
            <Input
              id="figma-url"
              required
              placeholder="https://www.figma.com/design/abc123/My-Prototype"
              value={figmaUrl}
              onChange={(e) => setFigmaUrl(e.target.value)}
            />
          </div>
          <Button type="submit" disabled={importFigmaMutation.isPending}>
            {importFigmaMutation.isPending ? "Importing…" : "Import"}
          </Button>
        </form>
        {importFigmaMutation.isError && (
          <p className="mt-3 text-[13px] text-semantic-warn">
            {importFigmaMutation.error instanceof Error
              ? importFigmaMutation.error.message
              : "Failed to import from Figma"}
          </p>
        )}
        {importFigmaMutation.isSuccess && (
          <p className="mt-3 text-[13px] text-ink-muted">
            Import started — screens will appear above once the background job finishes
            (refresh to check).
          </p>
        )}
      </Card>

      <Card>
        <CardTitle>Upload a screenshot</CardTitle>
        <p className="mt-2 text-[13px] text-ink-muted">
          A static screenshot — analyzed by a vision model to detect UI elements, since
          there&apos;s no structured source to read them from directly.
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
            <Label htmlFor="file">Image file</Label>
            <input
              id="file"
              type="file"
              required
              accept="image/*"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="text-[13px] text-ink-muted"
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
        {hasUnanalyzedScreenshot && (
          <div className="mt-4 border-t border-hairline pt-4">
            <Button
              type="button"
              variant="secondary"
              disabled={analyzeMutation.isPending}
              onClick={() => analyzeMutation.mutate()}
            >
              {analyzeMutation.isPending ? "Analyzing…" : "Analyze uploaded screenshots"}
            </Button>
            {analyzeMutation.isError && (
              <p className="mt-3 text-[13px] text-semantic-warn">
                {analyzeMutation.error instanceof Error
                  ? analyzeMutation.error.message
                  : "Failed to start analysis"}
              </p>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}
