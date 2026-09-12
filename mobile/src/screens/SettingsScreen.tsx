import { useState } from "react";
import {
  Alert,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";

import {
  getApiBaseUrl,
  getSupabaseAnonKey,
  getSupabaseUrl,
  setApiBaseUrl,
  setSupabaseConfig,
} from "../settings";

interface Props {
  onDone: () => void;
}

export function SettingsScreen({ onDone }: Props) {
  const [apiBaseUrl, setApiBaseUrlInput] = useState(getApiBaseUrl());
  const [supabaseUrl, setSupabaseUrlInput] = useState(getSupabaseUrl());
  const [supabaseAnonKey, setSupabaseAnonKeyInput] = useState(getSupabaseAnonKey());

  async function save() {
    const trimmedApiUrl = apiBaseUrl.trim().replace(/\/$/, "");
    if (!trimmedApiUrl) {
      Alert.alert("Enter a backend URL first");
      return;
    }
    await setApiBaseUrl(trimmedApiUrl);
    await setSupabaseConfig(supabaseUrl.trim().replace(/\/$/, ""), supabaseAnonKey.trim());
    onDone();
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.heading}>Backend address</Text>
      <Text style={styles.hint}>
        Where the FastAPI backend is running, e.g. http://192.168.1.42:8000. Find your
        computer's LAN IP and make sure uvicorn was started with --host 0.0.0.0.
      </Text>
      <TextInput
        style={styles.input}
        placeholder="http://192.168.1.42:8000"
        autoCapitalize="none"
        autoCorrect={false}
        keyboardType="url"
        value={apiBaseUrl}
        onChangeText={setApiBaseUrlInput}
      />

      <Text style={[styles.heading, styles.sectionSpacing]}>Supabase (creator sign-in only)</Text>
      <Text style={styles.hint}>
        Only needed for &quot;I&apos;m the study creator&quot; — Tester mode never uses this.
        Find these in the Supabase dashboard → Project Settings → API.
      </Text>
      <TextInput
        style={styles.input}
        placeholder="https://your-project.supabase.co"
        autoCapitalize="none"
        autoCorrect={false}
        keyboardType="url"
        value={supabaseUrl}
        onChangeText={setSupabaseUrlInput}
      />
      <TextInput
        style={styles.input}
        placeholder="Anon / public key"
        autoCapitalize="none"
        autoCorrect={false}
        value={supabaseAnonKey}
        onChangeText={setSupabaseAnonKeyInput}
      />

      <TouchableOpacity style={styles.button} onPress={save}>
        <Text style={styles.buttonText}>Save</Text>
      </TouchableOpacity>
      <TouchableOpacity onPress={onDone}>
        <Text style={styles.cancel}>Back</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flexGrow: 1, justifyContent: "center", padding: 24, gap: 12 },
  heading: { fontSize: 20, fontWeight: "700" },
  sectionSpacing: { marginTop: 12 },
  hint: { color: "#555", marginBottom: 8 },
  input: { borderWidth: 1, borderColor: "#ccc", borderRadius: 8, padding: 12 },
  button: { backgroundColor: "#1d4ed8", borderRadius: 10, padding: 16, alignItems: "center" },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  cancel: { textAlign: "center", color: "#555", marginTop: 8 },
});
