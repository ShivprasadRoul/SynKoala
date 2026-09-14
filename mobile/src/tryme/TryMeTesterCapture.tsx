import { useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { Button, Hint } from "./ui";
import { TryMeFigmaMockup } from "./TryMeFigmaMockup";
import { DEMO_TASK, TESTER_SESSION } from "./data";

export function TryMeTesterCapture({ onAdvance }: { onAdvance: () => void }) {
  const [finishing, setFinishing] = useState(false);

  function finish() {
    setFinishing(true);
    setTimeout(onAdvance, 500);
  }

  return (
    <View style={{ gap: 12 }}>
      <View style={styles.banner}>
        <Text style={styles.instruction}>{DEMO_TASK.instruction}</Text>
      </View>
      <TryMeFigmaMockup figmaUrl={TESTER_SESSION.captureToken} />
      <Hint>
        This is a live preview of the real prototype — tap around if you like, nothing you do
        here is recorded or sent anywhere.
      </Hint>
      <View style={styles.row}>
        <View style={styles.flex}>
          <Button label="Done — task completed" onPress={finish} loading={finishing} />
        </View>
        <View style={styles.flex}>
          <Button label="Give up" variant="danger" onPress={finish} disabled={finishing} />
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  banner: { padding: 12, backgroundColor: "#eff6ff", borderRadius: 10 },
  instruction: { fontWeight: "600", color: "#1e3a8a" },
  row: { flexDirection: "row", gap: 8 },
  flex: { flex: 1 },
});
