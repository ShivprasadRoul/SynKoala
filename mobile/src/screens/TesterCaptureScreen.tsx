import { useRef, useState } from "react";
import { ActivityIndicator, Alert, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { AudioModule, RecordingPresets, useAudioRecorder } from "expo-audio";

import { completeSession, submitObservation, uploadVoiceNote } from "../api/journeyCapture";
import { FigmaCaptureView } from "../components/FigmaCaptureView";

interface Props {
  captureToken: string;
  participantRunId: string;
  figmaUrl: string;
  instruction: string;
  onFinished: () => void;
}

/**
 * A recruited tester's blind attempt — unlike the creator's defined-path
 * walkthrough, every step posts immediately (planning/13-journey-capture.md).
 */
export function TesterCaptureScreen({
  captureToken,
  participantRunId,
  figmaUrl,
  instruction,
  onFinished,
}: Props) {
  const sequenceNo = useRef(0);
  const [stepCount, setStepCount] = useState(0);
  const [finishing, setFinishing] = useState(false);
  const [recording, setRecording] = useState(false);
  // expo-audio's hook/API shape here follows its documented usage as of this
  // writing — verify against the installed version before relying on it, same
  // as the Figma embed event shape in FigmaCaptureView.
  const audioRecorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);

  async function onStepCaptured(step: {
    screenFigmaNodeId: string;
    elementFigmaNodeId: string | null;
    action: "TAP" | "SCROLL" | "BACK";
    durationMs: number;
  }) {
    sequenceNo.current += 1;
    setStepCount(sequenceNo.current);
    try {
      await submitObservation(captureToken, participantRunId, {
        sequence_no: sequenceNo.current,
        type: step.action,
        screen_figma_node_id: step.screenFigmaNodeId,
        element_figma_node_id: step.elementFigmaNodeId,
        duration_ms: step.durationMs,
      });
    } catch (err) {
      Alert.alert("Failed to record step", err instanceof Error ? err.message : "Unknown error");
    }
  }

  async function toggleVoiceNote() {
    if (recording) {
      await audioRecorder.stop();
      setRecording(false);
      if (audioRecorder.uri) {
        try {
          await uploadVoiceNote(captureToken, participantRunId, audioRecorder.uri);
        } catch (err) {
          Alert.alert("Voice note upload failed", err instanceof Error ? err.message : "Unknown error");
        }
      }
      return;
    }
    const permission = await AudioModule.requestRecordingPermissionsAsync();
    if (!permission.granted) {
      Alert.alert("Microphone permission required to record a think-aloud note");
      return;
    }
    await audioRecorder.prepareToRecordAsync();
    audioRecorder.record();
    setRecording(true);
  }

  async function finish(outcomeStatus: "COMPLETED" | "ABANDONED") {
    setFinishing(true);
    try {
      await completeSession(captureToken, participantRunId, outcomeStatus, {
        reached_intended_path_end: outcomeStatus === "COMPLETED",
      });
      onFinished();
    } catch (err) {
      Alert.alert("Failed to finish session", err instanceof Error ? err.message : "Unknown error");
    } finally {
      setFinishing(false);
    }
  }

  return (
    <View style={styles.container}>
      <View style={styles.banner}>
        <Text style={styles.instruction}>{instruction || "Complete the task as instructed."}</Text>
      </View>
      <FigmaCaptureView figmaUrl={figmaUrl} onStep={onStepCaptured} />
      <View style={styles.footer}>
        <Text style={styles.stepCount}>{stepCount} step(s) sent</Text>
        <View style={styles.row}>
          <TouchableOpacity style={styles.secondaryButton} onPress={toggleVoiceNote}>
            <Text style={styles.buttonText}>{recording ? "Stop voice note" : "Record voice note"}</Text>
          </TouchableOpacity>
        </View>
        <View style={styles.row}>
          <TouchableOpacity
            style={styles.button}
            onPress={() => finish("COMPLETED")}
            disabled={finishing}
          >
            {finishing ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>Done — task completed</Text>}
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.button, styles.abandon]}
            onPress={() => finish("ABANDONED")}
            disabled={finishing}
          >
            <Text style={styles.buttonText}>Give up</Text>
          </TouchableOpacity>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  banner: { padding: 12, backgroundColor: "#eff6ff" },
  instruction: { fontWeight: "600" },
  footer: { padding: 12, gap: 8, borderTopWidth: 1, borderTopColor: "#ddd" },
  stepCount: { textAlign: "center", color: "#555" },
  row: { flexDirection: "row", gap: 8 },
  button: {
    flex: 1,
    backgroundColor: "#1d4ed8",
    borderRadius: 10,
    padding: 16,
    alignItems: "center",
  },
  secondaryButton: {
    flex: 1,
    backgroundColor: "#334155",
    borderRadius: 10,
    padding: 12,
    alignItems: "center",
  },
  abandon: { backgroundColor: "#b91c1c" },
  buttonText: { color: "#fff", fontSize: 15, fontWeight: "600" },
});
