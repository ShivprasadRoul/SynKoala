import { useState } from "react";
import {
  ActivityIndicator,
  Alert,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";

import { createSimulationRun, submitIntendedPath } from "../api/journeyCapture";
import { FigmaCaptureView, type CapturedStep } from "../components/FigmaCaptureView";
import type { Study, Task } from "../types";

interface Props {
  token: string;
  study: Study;
  task: Task;
  onDone: () => void;
}

/**
 * The creator's own one-time walkthrough — steps are buffered locally and
 * submitted as one call at the end (planning/13-journey-capture.md: "not
 * streamed live, nothing needs to watch the creator's own walkthrough").
 */
export function DefinedPathCaptureScreen({ token, study, task, onDone }: Props) {
  const [figmaUrl, setFigmaUrl] = useState("");
  const [started, setStarted] = useState(false);
  const [steps, setSteps] = useState<CapturedStep[]>([]);
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    setSubmitting(true);
    try {
      await submitIntendedPath(
        token,
        study.id,
        task.id,
        steps.map((s) => ({
          screen_figma_node_id: s.screenFigmaNodeId,
          element_figma_node_id: s.elementFigmaNodeId,
          action: s.action,
          duration_ms: s.durationMs,
        }))
      );
    } catch (err) {
      setSubmitting(false);
      Alert.alert("Failed to submit", err instanceof Error ? err.message : "Unknown error");
      return;
    }

    // The study is already confirmed READY before this screen is reachable
    // (CreatorPickerScreen gates it) — only the sample size can still be
    // missing, since it's optional at study creation.
    if (!study.population_size) {
      setSubmitting(false);
      Alert.alert(
        "Path saved",
        "The defined path was saved, but this study has no sample size set (set it on the study in the web dashboard) — start the simulation from there instead."
      );
      onDone();
      return;
    }

    try {
      await createSimulationRun(token, study.id, {
        population_size: study.population_size,
        task_id: task.id,
      });
      Alert.alert("Path saved", `Simulation started for ${study.population_size} participants.`);
    } catch (err) {
      Alert.alert(
        "Path saved, but the simulation didn't start",
        err instanceof Error ? err.message : "Unknown error"
      );
    } finally {
      setSubmitting(false);
      onDone();
    }
  }

  if (!started) {
    return (
      <View style={styles.setup}>
        <Text style={styles.heading}>Paste the Figma prototype link</Text>
        <TextInput
          style={styles.input}
          placeholder="https://www.figma.com/proto/..."
          autoCapitalize="none"
          value={figmaUrl}
          onChangeText={setFigmaUrl}
        />
        <TouchableOpacity
          style={styles.button}
          disabled={!figmaUrl.trim()}
          onPress={() => setStarted(true)}
        >
          <Text style={styles.buttonText}>Start walkthrough</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <FigmaCaptureView figmaUrl={figmaUrl} onStep={(step) => setSteps((prev) => [...prev, step])} />
      <View style={styles.footer}>
        <Text style={styles.stepCount}>{steps.length} step(s) recorded</Text>
        <TouchableOpacity style={styles.button} onPress={submit} disabled={submitting || steps.length === 0}>
          {submitting ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.buttonText}>Finish & submit</Text>
          )}
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  setup: { flex: 1, justifyContent: "center", padding: 24, gap: 12 },
  heading: { fontSize: 18, fontWeight: "700" },
  input: { borderWidth: 1, borderColor: "#ccc", borderRadius: 8, padding: 12 },
  footer: { padding: 12, gap: 8, borderTopWidth: 1, borderTopColor: "#ddd" },
  stepCount: { textAlign: "center", color: "#555" },
  button: { backgroundColor: "#1d4ed8", borderRadius: 10, padding: 16, alignItems: "center" },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "600" },
});
