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

import { createCaptureSession, createHumanRun } from "../api/journeyCapture";
import type { Study, Task } from "../types";

interface Props {
  token: string;
  study: Study;
  task: Task;
  onHandOffToTester: (params: {
    captureToken: string;
    participantRunId: string;
    figmaUrl: string;
    instruction: string;
  }) => void;
}

/**
 * No bootstrap endpoint exists for a tester's device to fetch the Figma link
 * from a bare capture token (planning/13-journey-capture.md's route list is
 * write-only) — the creator hands off the token, the Figma link, and the
 * instruction together, out of band, exactly as the design describes.
 */
export function StartTesterSessionScreen({ token, study, task, onHandOffToTester }: Props) {
  const [testerLabel, setTesterLabel] = useState("");
  const [figmaUrl, setFigmaUrl] = useState("");
  const [session, setSession] = useState<{ captureToken: string; participantRunId: string } | null>(
    null
  );
  const [loading, setLoading] = useState(false);

  async function startSession() {
    setLoading(true);
    try {
      const run = await createHumanRun(token, study.id, task.id);
      const created = await createCaptureSession(token, run.id, testerLabel.trim() || null);
      setSession({ captureToken: created.capture_token, participantRunId: created.participant_run_id });
    } catch (err) {
      Alert.alert("Failed to start session", err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  if (!session) {
    return (
      <View style={styles.container}>
        <Text style={styles.heading}>Start a tester session</Text>
        <TextInput
          style={styles.input}
          placeholder="Tester label (optional, e.g. first-time-buyer-01)"
          value={testerLabel}
          onChangeText={setTesterLabel}
        />
        <TextInput
          style={styles.input}
          placeholder="Figma prototype link (to hand to the tester)"
          autoCapitalize="none"
          value={figmaUrl}
          onChangeText={setFigmaUrl}
        />
        <TouchableOpacity style={styles.button} onPress={startSession} disabled={loading}>
          {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>Start session</Text>}
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.heading}>Session ready</Text>
      <Text style={styles.hint}>
        Share this token and run id with the tester (plus the Figma link and task instruction), or
        hand them this device now:
      </Text>
      <Text selectable style={styles.token}>
        {session.captureToken}
      </Text>
      <Text selectable style={styles.token}>
        {session.participantRunId}
      </Text>
      <TouchableOpacity
        style={styles.button}
        onPress={() =>
          onHandOffToTester({
            captureToken: session.captureToken,
            participantRunId: session.participantRunId,
            figmaUrl,
            instruction: task.instruction,
          })
        }
      >
        <Text style={styles.buttonText}>Hand device to tester now</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 24, gap: 12, justifyContent: "center" },
  heading: { fontSize: 18, fontWeight: "700" },
  hint: { color: "#555" },
  input: { borderWidth: 1, borderColor: "#ccc", borderRadius: 8, padding: 12 },
  token: {
    fontFamily: "monospace",
    backgroundColor: "#f1f5f9",
    padding: 12,
    borderRadius: 8,
    fontSize: 12,
  },
  button: { backgroundColor: "#1d4ed8", borderRadius: 10, padding: 16, alignItems: "center" },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "600" },
});
