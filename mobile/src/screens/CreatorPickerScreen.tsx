import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";

import { listStudies, listTasks } from "../api/journeyCapture";
import type { Study, Task } from "../types";

interface Props {
  token: string;
  onRecordDefinedPath: (study: Study, task: Task) => void;
  onStartTesterSession: (study: Study, task: Task) => void;
}

export function CreatorPickerScreen({ token, onRecordDefinedPath, onStartTesterSession }: Props) {
  const [studies, setStudies] = useState<Study[] | null>(null);
  const [tasks, setTasks] = useState<Task[] | null>(null);
  const [selectedStudy, setSelectedStudy] = useState<Study | null>(null);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listStudies(token)
      .then(setStudies)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load studies"));
  }, [token]);

  function selectStudy(study: Study) {
    setSelectedStudy(study);
    setSelectedTask(null);
    setTasks(null);
    listTasks(token, study.id)
      .then(setTasks)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load tasks"));
  }

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.error}>{error}</Text>
      </View>
    );
  }

  if (!selectedStudy) {
    if (!studies) return <ActivityIndicator style={styles.center} />;
    return (
      <View style={styles.container}>
        <Text style={styles.heading}>Select a study</Text>
        <FlatList
          data={studies}
          keyExtractor={(s) => s.id}
          renderItem={({ item }) => (
            <TouchableOpacity style={styles.row} onPress={() => selectStudy(item)}>
              <Text style={styles.rowTitle}>{item.name}</Text>
              <Text style={styles.rowSubtitle}>{item.status}</Text>
            </TouchableOpacity>
          )}
          ListEmptyComponent={
            <Text style={styles.empty}>
              No studies yet for this account. Create one from the web research dashboard first.
            </Text>
          }
        />
      </View>
    );
  }

  if (!selectedTask) {
    if (!tasks) return <ActivityIndicator style={styles.center} />;
    return (
      <View style={styles.container}>
        <Text style={styles.heading}>Select a task</Text>
        <FlatList
          data={tasks}
          keyExtractor={(t) => t.id}
          renderItem={({ item }) => (
            <TouchableOpacity style={styles.row} onPress={() => setSelectedTask(item)}>
              <Text style={styles.rowTitle}>{item.instruction}</Text>
            </TouchableOpacity>
          )}
          ListEmptyComponent={
            <Text style={styles.empty}>
              No tasks yet for this study. Create one from the web research dashboard first.
            </Text>
          }
        />
      </View>
    );
  }

  const isReady = selectedStudy.status === "READY";

  return (
    <View style={styles.container}>
      <Text style={styles.heading}>{selectedTask.instruction}</Text>
      {isReady ? (
        <TouchableOpacity
          style={styles.button}
          onPress={() => onRecordDefinedPath(selectedStudy, selectedTask)}
        >
          <Text style={styles.buttonText}>Record defined path</Text>
        </TouchableOpacity>
      ) : (
        <Text style={styles.notReady}>
          This study is {selectedStudy.status.toLowerCase()}, not READY yet — finish setting up
          the audience, task, and stimulus in the web dashboard and mark it READY before
          recording a defined path here (recording one auto-starts a simulation run, which
          needs the study to be READY).
        </Text>
      )}
      <TouchableOpacity
        style={[styles.button, styles.secondary]}
        onPress={() => onStartTesterSession(selectedStudy, selectedTask)}
      >
        <Text style={styles.buttonText}>Start human tester session</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 24, gap: 12 },
  center: { flex: 1, justifyContent: "center", alignItems: "center" },
  heading: { fontSize: 18, fontWeight: "700", marginBottom: 8 },
  row: { paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: "#eee" },
  rowTitle: { fontSize: 16, fontWeight: "600" },
  rowSubtitle: { color: "#777" },
  error: { color: "#b91c1c", padding: 24 },
  empty: { color: "#777", paddingTop: 24, textAlign: "center" },
  notReady: { color: "#a15a00", lineHeight: 20 },
  button: { backgroundColor: "#1d4ed8", borderRadius: 10, padding: 16, alignItems: "center" },
  secondary: { backgroundColor: "#334155" },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "600" },
});
