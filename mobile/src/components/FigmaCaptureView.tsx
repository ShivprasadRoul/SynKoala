import { useEffect, useMemo, useRef, useState } from "react";
import { Animated, StyleSheet, Text, TextInput, TouchableOpacity, View } from "react-native";
import { WebView, type WebViewMessageEvent } from "react-native-webview";

import type { CapturedAction } from "../types";

export interface CapturedStep {
  screenFigmaNodeId: string;
  elementFigmaNodeId: string | null;
  action: CapturedAction;
  durationMs: number;
}

interface Props {
  figmaUrl: string;
  onStep: (step: CapturedStep) => void;
}

function buildEmbedHtml(figmaUrl: string): string {
  const embedSrc = `https://www.figma.com/embed?embed_host=synkoala&url=${encodeURIComponent(figmaUrl)}`;
  return `<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1">
    <style>html,body,#figma-embed{margin:0;padding:0;height:100%;width:100%;border:none;}</style>
  </head><body>
    <iframe id="figma-embed" src="${embedSrc}" allowfullscreen></iframe>
    <script>
      window.addEventListener('message', function (event) {
        // Forward EVERY message, not just the ones we recognize — the RN
        // side logs the raw payload so we can see exactly what Figma's
        // embed actually sends (its real event shape is unverified against
        // a live prototype, see the component doc comment below).
        window.ReactNativeWebView.postMessage(JSON.stringify({
          origin: event.origin,
          data: event.data,
        }));
      });
    </script>
  </body></html>`;
}

/**
 * Embeds Figma's prototype player (Embed Kit 2.0). Two capture mechanisms run
 * side by side right now:
 *
 * 1. Automatic — every postMessage from the embed is logged (visible via
 *    `adb logcat | grep ReactNativeJS` while testing) and scanned for a
 *    node-id-shaped field. This is unverified against a real prototype:
 *    Figma's actual event name/payload shape may not match what's assumed
 *    here, which is exactly why steps weren't recording automatically.
 * 2. Manual fallback — Log Tap/Scroll/Back buttons + a node-id field, kept
 *    so a capture session is never fully blocked while the automatic side
 *    gets diagnosed against real usage.
 *
 * A Figma file gated behind "must be logged in to view" will show Figma's own
 * login screen here — there's no way to bypass that with a cached API token
 * (the backend's Figma OAuth token authenticates REST API calls, not this
 * WebView's browser session; they're unrelated auth systems). The prototype
 * being captured must be shared as "Anyone with the link can view" in Figma,
 * since human testers never have a Figma account either.
 */
export function FigmaCaptureView({ figmaUrl, onStep }: Props) {
  const html = useMemo(() => buildEmbedHtml(figmaUrl), [figmaUrl]);
  const lastStepAt = useRef(Date.now());
  const [pendingNodeId, setPendingNodeId] = useState("");

  // A pulsing red border + badge around the prototype view — the visible
  // signal that a capture session is actively recording, for as long as this
  // component is mounted (both the creator's buffered walkthrough and a
  // tester's live session render it only while capturing is in progress).
  const pulse = useRef(new Animated.Value(1)).current;
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 0.35, duration: 700, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 1, duration: 700, useNativeDriver: true }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, [pulse]);

  function logStep(action: CapturedAction, nodeIdOverride?: string) {
    const now = Date.now();
    const durationMs = now - lastStepAt.current;
    lastStepAt.current = now;
    onStep({
      screenFigmaNodeId: nodeIdOverride ?? (pendingNodeId.trim() || "unknown"),
      elementFigmaNodeId: null,
      action,
      durationMs,
    });
  }

  // Best-effort scan for anything node-id-shaped in an unrecognized payload,
  // so a differently-named Figma event still has a chance of being caught
  // automatically instead of silently doing nothing.
  function findNodeId(data: unknown): string | null {
    if (!data || typeof data !== "object") return null;
    for (const [key, value] of Object.entries(data as Record<string, unknown>)) {
      if (typeof value === "string" && /node/i.test(key) && /id/i.test(key)) return value;
      if (value && typeof value === "object") {
        const nested = findNodeId(value);
        if (nested) return nested;
      }
    }
    return null;
  }

  function handleMessage(event: WebViewMessageEvent) {
    let parsed: { origin?: string; data?: unknown };
    try {
      parsed = JSON.parse(event.nativeEvent.data);
    } catch {
      return;
    }
    // Visible via `adb logcat | grep ReactNativeJS` — the actual diagnostic
    // signal while Figma's real embed event shape is unverified.
    console.log("FigmaCaptureView raw message:", JSON.stringify(parsed));

    const data = parsed?.data as { type?: string; data?: { presentedNodeId?: string } } | undefined;
    if (data?.type === "PRESENTED_NODE_CHANGED" && data?.data?.presentedNodeId) {
      logStep("TAP", data.data.presentedNodeId);
      return;
    }
    const fallbackNodeId = findNodeId(parsed?.data);
    if (fallbackNodeId) {
      logStep("TAP", fallbackNodeId);
    }
  }

  return (
    <View style={styles.container}>
      <View style={styles.webviewWrapper}>
        <WebView
          source={{ html }}
          onMessage={handleMessage}
          javaScriptEnabled
          domStorageEnabled
          thirdPartyCookiesEnabled
          sharedCookiesEnabled
          style={styles.webview}
        />
        <Animated.View pointerEvents="none" style={[styles.recordingBorder, { opacity: pulse }]} />
        <View pointerEvents="none" style={styles.recordingBadge}>
          <Text style={styles.recordingBadgeText}>● Capturing</Text>
        </View>
      </View>
      <View style={styles.controls}>
        <TextInput
          style={styles.input}
          placeholder="Figma node id (manual fallback)"
          value={pendingNodeId}
          onChangeText={setPendingNodeId}
          autoCapitalize="none"
        />
        <View style={styles.buttonRow}>
          <TouchableOpacity style={styles.button} onPress={() => logStep("TAP")}>
            <Text style={styles.buttonText}>Log Tap</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.button} onPress={() => logStep("SCROLL")}>
            <Text style={styles.buttonText}>Log Scroll</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.button} onPress={() => logStep("BACK")}>
            <Text style={styles.buttonText}>Log Back</Text>
          </TouchableOpacity>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  webviewWrapper: { flex: 1, position: "relative" },
  webview: { flex: 1 },
  recordingBorder: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    borderWidth: 4,
    borderColor: "#dc2626",
  },
  recordingBadge: {
    position: "absolute",
    top: 10,
    left: 10,
    backgroundColor: "#dc2626",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
  },
  recordingBadgeText: { color: "#fff", fontSize: 12, fontWeight: "700" },
  controls: { padding: 12, borderTopWidth: 1, borderTopColor: "#ddd", gap: 8 },
  input: { borderWidth: 1, borderColor: "#ccc", borderRadius: 8, padding: 8 },
  buttonRow: { flexDirection: "row", gap: 8 },
  button: {
    flex: 1,
    backgroundColor: "#1d4ed8",
    borderRadius: 8,
    padding: 10,
    alignItems: "center",
  },
  buttonText: { color: "#fff", fontWeight: "600" },
});
