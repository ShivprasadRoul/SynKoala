import { useState } from "react";
import { StyleSheet, Text, TextInput, TouchableOpacity, View } from "react-native";

interface Props {
  onEnter: (params: {
    captureToken: string;
    participantRunId: string;
    figmaUrl: string;
    instruction: string;
  }) => void;
  onCancel: () => void;
}

export function TesterEntryScreen({ onEnter, onCancel }: Props) {
  const [captureToken, setCaptureToken] = useState("");
  const [participantRunId, setParticipantRunId] = useState("");
  const [figmaUrl, setFigmaUrl] = useState("");
  const [instruction, setInstruction] = useState("");

  const canContinue =
    captureToken.trim().length > 0 && participantRunId.trim().length > 0 && figmaUrl.trim().length > 0;

  return (
    <View style={styles.container}>
      <Text style={styles.heading}>Enter your session details</Text>
      <Text style={styles.hint}>The study creator gave you these.</Text>
      <TextInput
        style={styles.input}
        placeholder="Capture token"
        autoCapitalize="none"
        value={captureToken}
        onChangeText={setCaptureToken}
      />
      <TextInput
        style={styles.input}
        placeholder="Participant run id"
        autoCapitalize="none"
        value={participantRunId}
        onChangeText={setParticipantRunId}
      />
      <TextInput
        style={styles.input}
        placeholder="Figma prototype link"
        autoCapitalize="none"
        value={figmaUrl}
        onChangeText={setFigmaUrl}
      />
      <TextInput
        style={styles.input}
        placeholder="Task instruction (optional, for your reference)"
        value={instruction}
        onChangeText={setInstruction}
      />
      <TouchableOpacity
        style={styles.button}
        disabled={!canContinue}
        onPress={() =>
          onEnter({
            captureToken: captureToken.trim(),
            participantRunId: participantRunId.trim(),
            figmaUrl: figmaUrl.trim(),
            instruction: instruction.trim(),
          })
        }
      >
        <Text style={styles.buttonText}>Begin task</Text>
      </TouchableOpacity>
      <TouchableOpacity onPress={onCancel}>
        <Text style={styles.cancel}>Back</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: "center", padding: 24, gap: 12 },
  heading: { fontSize: 20, fontWeight: "700" },
  hint: { color: "#555", marginBottom: 8 },
  input: { borderWidth: 1, borderColor: "#ccc", borderRadius: 8, padding: 12 },
  button: { backgroundColor: "#1d4ed8", borderRadius: 10, padding: 16, alignItems: "center" },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  cancel: { textAlign: "center", color: "#555", marginTop: 8 },
});
