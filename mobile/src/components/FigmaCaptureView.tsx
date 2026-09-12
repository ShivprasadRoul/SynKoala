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
        if (event.data && typeof event.data === 'object' && event.data.type) {
          window.ReactNativeWebView.postMessage(JSON.stringify(event.data));
        }
      });
    </script>
  </body></html>`;
}

/**
 * Embeds Figma's prototype player (Embed Kit 2.0) and turns its postMessage
 * events into captured steps, with a manual fallback for node ids the embed
 * doesn't surface. planning/13-journey-capture.md flags verifying the
 * PRESENTED_NODE_CHANGED payload shape against a real prototype as an early
 * spike — this hasn't been exercised against a live Figma file yet.
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

  function handleMessage(event: WebViewMessageEvent) {
    try {
      const data = JSON.parse(event.nativeEvent.data);
      if (data?.type === "PRESENTED_NODE_CHANGED" && data?.data?.presentedNodeId) {
        logStep("TAP", data.data.presentedNodeId as string);
      }
    } catch {
      // Non-JSON or unrelated postMessage traffic from the embed — ignore.
    }
  }

  return (
    <View style={styles.container}>
      <View style={styles.webviewWrapper}>
        <WebView
          source={{ html }}
          onMessage={handleMessage}
          javaScriptEnabled
          style={styles.webview}
        />
        <Animated.View
          pointerEvents="none"
          style={[styles.recordingBorder, { opacity: pulse }]}
        />
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
