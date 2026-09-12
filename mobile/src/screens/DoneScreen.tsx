import { StyleSheet, Text, TouchableOpacity, View } from "react-native";

interface Props {
  message: string;
  onRestart: () => void;
}

export function DoneScreen({ message, onRestart }: Props) {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Done</Text>
      <Text style={styles.message}>{message}</Text>
      <TouchableOpacity style={styles.button} onPress={onRestart}>
        <Text style={styles.buttonText}>Back to start</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: "center", alignItems: "center", padding: 24, gap: 16 },
  title: { fontSize: 24, fontWeight: "700" },
  message: { textAlign: "center", color: "#555" },
  button: { backgroundColor: "#1d4ed8", borderRadius: 10, padding: 16, paddingHorizontal: 24 },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "600" },
});
