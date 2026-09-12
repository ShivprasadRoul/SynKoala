"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useState } from "react";

import { getFigmaAuthorizeUrl } from "@/lib/api/auth";
import { analyzeStimuli, listStimuli, uploadStimulus } from "@/lib/api/stimulus";

import { Button } from "@/components/ui/Button";
import { Card, CardDescription, CardTitle } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
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

  const allScreens = (stimuli ?? []).flatMap((s) => s.screens.map((screen) => ({ stimulus: s, screen })));
  const hasUnanalyzedScreenshot = (stimuli ?? []).some(
    (s) => s.type !== "figma" && s.screens.every((screen) => screen.elements.length === 0)
  );

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h2 className="font-display text-[18px] font-bold text-ink">Add your product experience</h2>
        <p className="mt-1 text-[13px] text-ink-muted">
          Import the interface SynKoala will test — from Figma directly, or a screenshot.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card className="flex flex-col">
          <div className="flex items-center justify-between">
            <CardTitle>Import from Figma</CardTitle>
            <button
              type="button"
              onClick={() => connectFigmaMutation.mutate()}
              className="text-[12px] font-semibold text-ink-muted transition-colors hover:text-ink"
            >
              {connectFigmaMutation.isPending ? "Redirecting…" : "Connect Figma"}
            </button>
          </div>
          <CardDescription className="mt-2">
            Fetches every frame in the file directly from Figma — real bounding boxes and
            navigation links, no screenshot needed. The file must be shared as &quot;Anyone with
            the link can view&quot;, since it&apos;s viewed via API without a Figma login.
          </CardDescription>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              importFigmaMutation.mutate();
            }}
            className="mt-5 flex flex-1 flex-col justify-end gap-3"
          >
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="figma-url">Prototype URL</Label>
              <Input
                id="figma-url"
                required
                placeholder="https://www.figma.com/design/abc123/My-Prototype"
                value={figmaUrl}
                onChange={(e) => setFigmaUrl(e.target.value)}
              />
            </div>
            <Button type="submit" disabled={importFigmaMutation.isPending} className="self-start">
              {importFigmaMutation.isPending ? "Importing…" : "Import prototype"}
            </Button>
            {importFigmaMutation.isError && (
              <p className="text-[13px] text-semantic-warn">
                {importFigmaMutation.error instanceof Error
                  ? importFigmaMutation.error.message
                  : "Failed to import from Figma"}
              </p>
            )}
            {importFigmaMutation.isSuccess && (
              <p className="text-[12px] text-ink-tertiary">
                Import started — screens will appear below once the background job finishes.
              </p>
            )}
          </form>
        </Card>

        <Card className="flex flex-col">
          <CardTitle>Upload a screenshot</CardTitle>
          <CardDescription className="mt-2">
            A static screenshot — analyzed by a vision model to detect UI elements, since
            there&apos;s no structured source to read them from directly.
          </CardDescription>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              uploadMutation.mutate();
            }}
            className="mt-5 flex flex-1 flex-col justify-end gap-3"
          >
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
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
                  className="rounded-md border border-hairline bg-surface-card px-3 py-2 text-[13px] text-ink-muted shadow-sm"
                />
              </div>
            </div>
            {uploadMutation.isError && (
              <p className="text-[13px] text-semantic-warn">
                {uploadMutation.error instanceof Error
                  ? uploadMutation.error.message
                  : "Failed to upload stimulus"}
              </p>
            )}
            <Button
              type="submit"
              variant="secondary"
              disabled={uploadMutation.isPending}
              className="self-start"
            >
              {uploadMutation.isPending ? "Uploading…" : "Upload screenshot"}
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

      <div>
        <div className="mb-3 flex items-baseline justify-between">
          <h3 className="text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-tertiary">
            Stimulus
          </h3>
          {allScreens.length > 0 && (
            <span className="font-mono text-[12px] tabular-nums text-ink-tertiary">
              {allScreens.length} screen{allScreens.length === 1 ? "" : "s"} imported
            </span>
          )}
        </div>

        {allScreens.length === 0 ? (
          <EmptyState
            title="No screens yet"
            description="Import a Figma prototype or upload a screenshot above to see it here."
          />
        ) : (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
            {allScreens.map(({ stimulus, screen }) => (
              <Card key={screen.id} className="flex flex-col gap-2 p-3">
                <div className="flex aspect-video items-center justify-center overflow-hidden rounded-md bg-surface-2">
                  {screen.image_url ? (
                    // eslint-disable-next-line @next/next/no-img-element -- external Supabase Storage URL, not a static/local asset next/image can optimize
                    <img
                      src={screen.image_url}
                      alt={screen.screen_key}
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <span className="text-[11px] text-ink-tertiary">No preview</span>
                  )}
                </div>
                <p className="truncate text-[13px] font-semibold text-ink" title={screen.screen_key}>
                  {screen.screen_key}
                </p>
                <p className="text-[11px] text-ink-tertiary">
                  {screen.width && screen.height ? `${screen.width}×${screen.height} · ` : ""}
                  {screen.elements.length} element{screen.elements.length === 1 ? "" : "s"}
                </p>
                <span className="w-fit rounded-full bg-surface-1 px-2 py-0.5 text-[10px] uppercase tracking-[0.04em] text-ink-tertiary">
                  {stimulus.type}
                </span>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
