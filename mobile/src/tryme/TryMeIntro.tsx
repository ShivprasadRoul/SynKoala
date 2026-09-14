import { StyleSheet, Text, View } from "react-native";
import { Button } from "./ui";

export function TryMeIntro({
  onPickTrack,
  onExit,
}: {
  onPickTrack: (track: "creator" | "tester") => void;
  onExit: () => void;
}) {
  return (
    <View style={styles.container}>
      <Text style={styles.badge}>TRY ME · DEMO</Text>
      <Text style={styles.title}>SynKoala Journey Capture</Text>
      <Text style={styles.subtitle}>
        A guided, static walkthrough of the real app — no sign-up, nothing real is sent
        anywhere. Pick a side to begin.
      </Text>
      <View style={styles.buttons}>
        <Button label="I'm the study creator" onPress={() => onPickTrack("creator")} />
        <Button label="I have a tester code" variant="secondary" onPress={() => onPickTrack("tester")} />
      </View>
      <Text style={styles.exit} onPress={onExit}>
        Exit demo
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: "center", padding: 24, gap: 12 },
  badge: {
    alignSelf: "center",
    fontSize: 11,
    fontWeight: "700",
    color: "#666",
    letterSpacing: 0.6,
    backgroundColor: "#f1f5f9",
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 4,
    marginBottom: 8,
  },
  title: { fontSize: 24, fontWeight: "700", textAlign: "center" },
  subtitle: { fontSize: 14, color: "#555", textAlign: "center", marginBottom: 8, lineHeight: 20 },
  buttons: { gap: 10 },
  exit: { textAlign: "center", color: "#888", marginTop: 16, fontSize: 13 },
});
