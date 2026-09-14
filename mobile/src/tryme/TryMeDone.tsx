import { StyleSheet, Text, View } from "react-native";
import { Button } from "./ui";

export function TryMeDone({
  message,
  onRestart,
  onExit,
}: {
  message: string;
  onRestart: () => void;
  onExit: () => void;
}) {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Done</Text>
      <Text style={styles.message}>{message}</Text>
      <View style={styles.buttons}>
        <Button label="Try the other flow" variant="secondary" onPress={onRestart} />
        <Button label="Exit demo" onPress={onExit} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: "center", alignItems: "center", padding: 24, gap: 16 },
  title: { fontSize: 24, fontWeight: "700" },
  message: { textAlign: "center", color: "#555" },
  buttons: { width: "100%", gap: 10, marginTop: 8 },
});
