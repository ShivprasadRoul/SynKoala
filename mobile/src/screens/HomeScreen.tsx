import { StyleSheet, Text, TouchableOpacity, View } from "react-native";

interface Props {
  onSelectCreator: () => void;
  onSelectTester: () => void;
}

export function HomeScreen({ onSelectCreator, onSelectTester }: Props) {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>SynKoala Journey Capture</Text>
      <Text style={styles.subtitle}>
        Record a defined journey, or attempt a task as a recruited tester.
      </Text>
      <TouchableOpacity style={styles.button} onPress={onSelectCreator}>
        <Text style={styles.buttonText}>I'm the study creator</Text>
      </TouchableOpacity>
      <TouchableOpacity style={[styles.button, styles.secondary]} onPress={onSelectTester}>
        <Text style={styles.buttonText}>I have a tester code</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: "center", padding: 24, gap: 16 },
  title: { fontSize: 24, fontWeight: "700", textAlign: "center" },
  subtitle: { fontSize: 14, color: "#555", textAlign: "center", marginBottom: 16 },
  button: {
    backgroundColor: "#1d4ed8",
    borderRadius: 10,
    padding: 16,
    alignItems: "center",
  },
  secondary: { backgroundColor: "#334155" },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "600" },
});
