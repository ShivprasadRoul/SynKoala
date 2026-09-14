import type { ReactNode } from "react";
import { ActivityIndicator, StyleSheet, Text, TouchableOpacity, View } from "react-native";

// Shared building blocks for the Try Me demo, matching the real app's own
// (deliberately plain) palette — #1d4ed8 primary blue, #334155 secondary
// slate — rather than inventing a nicer design the shipped app doesn't have.

export function Heading({ children }: { children: ReactNode }) {
  return <Text style={styles.heading}>{children}</Text>;
}

export function Hint({ children }: { children: ReactNode }) {
  return <Text style={styles.hint}>{children}</Text>;
}

export function FakeInput({ label, value, secure = false }: { label: string; value: string; secure?: boolean }) {
  return (
    <View style={styles.fakeInput}>
      <Text style={styles.fakeInputLabel}>{label}</Text>
      <Text style={styles.fakeInputValue}>{secure ? "••••••••••" : value}</Text>
    </View>
  );
}

export function Card({ children }: { children: ReactNode }) {
  return <View style={styles.card}>{children}</View>;
}

export function Button({
  label,
  onPress,
  variant = "primary",
  loading = false,
  disabled = false,
}: {
  label: string;
  onPress: () => void;
  variant?: "primary" | "secondary" | "danger";
  loading?: boolean;
  disabled?: boolean;
}) {
  const variantStyle =
    variant === "secondary" ? styles.secondary : variant === "danger" ? styles.danger : styles.primary;
  return (
    <TouchableOpacity
      style={[styles.button, variantStyle, disabled && styles.disabled]}
      onPress={onPress}
      disabled={disabled || loading}
    >
      {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>{label}</Text>}
    </TouchableOpacity>
  );
}

export function StepList({ steps, activeCount }: { steps: string[]; activeCount: number }) {
  return (
    <View style={styles.stepList}>
      {steps.slice(0, activeCount).map((step, i) => (
        <View key={i} style={styles.stepRow}>
          <View style={styles.stepDot} />
          <Text style={styles.stepText}>{step}</Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  heading: { fontSize: 18, fontWeight: "700", color: "#111" },
  hint: { color: "#555", lineHeight: 20 },
  card: {
    backgroundColor: "#f8fafc",
    borderWidth: 1,
    borderColor: "#e2e8f0",
    borderRadius: 12,
    padding: 16,
    gap: 10,
  },
  fakeInput: {
    borderWidth: 1,
    borderColor: "#ccc",
    borderRadius: 8,
    padding: 12,
    backgroundColor: "#fff",
  },
  fakeInputLabel: { fontSize: 11, color: "#888", marginBottom: 2 },
  fakeInputValue: { fontSize: 15, color: "#333" },
  button: { borderRadius: 10, padding: 16, alignItems: "center" },
  primary: { backgroundColor: "#1d4ed8" },
  secondary: { backgroundColor: "#334155" },
  danger: { backgroundColor: "#b91c1c" },
  disabled: { opacity: 0.5 },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  stepList: { gap: 8 },
  stepRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  stepDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: "#1d4ed8" },
  stepText: { fontSize: 14, color: "#333" },
});
