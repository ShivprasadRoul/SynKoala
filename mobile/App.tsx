import { useState } from "react";
import { SafeAreaView, StatusBar, StyleSheet } from "react-native";

import { CreatorLoginScreen } from "./src/screens/CreatorLoginScreen";
import { CreatorPickerScreen } from "./src/screens/CreatorPickerScreen";
import { DefinedPathCaptureScreen } from "./src/screens/DefinedPathCaptureScreen";
import { DoneScreen } from "./src/screens/DoneScreen";
import { HomeScreen } from "./src/screens/HomeScreen";
import { StartTesterSessionScreen } from "./src/screens/StartTesterSessionScreen";
import { TesterCaptureScreen } from "./src/screens/TesterCaptureScreen";
import { TesterEntryScreen } from "./src/screens/TesterEntryScreen";
import type { Study, Task } from "./src/types";

type AppScreen =
  | { name: "home" }
  | { name: "creator-login" }
  | { name: "creator-picker"; token: string }
  | { name: "defined-path"; token: string; study: Study; task: Task }
  | { name: "start-session"; token: string; study: Study; task: Task }
  | { name: "tester-entry" }
  | {
      name: "tester-capture";
      captureToken: string;
      participantRunId: string;
      figmaUrl: string;
      instruction: string;
    }
  | { name: "done"; message: string };

// This app deliberately doesn't use a navigation library — a half-dozen
// linear screens don't need one, and it keeps the toolchain minimal
// (planning/13-journey-capture.md: least dev-environment overhead).
export default function App() {
  const [screen, setScreen] = useState<AppScreen>({ name: "home" });

  let content;
  switch (screen.name) {
    case "home":
      content = (
        <HomeScreen
          onSelectCreator={() => setScreen({ name: "creator-login" })}
          onSelectTester={() => setScreen({ name: "tester-entry" })}
        />
      );
      break;
    case "creator-login":
      content = (
        <CreatorLoginScreen
          onLoggedIn={(token) => setScreen({ name: "creator-picker", token })}
          onCancel={() => setScreen({ name: "home" })}
        />
      );
      break;
    case "creator-picker":
      content = (
        <CreatorPickerScreen
          token={screen.token}
          onRecordDefinedPath={(study, task) =>
            setScreen({ name: "defined-path", token: screen.token, study, task })
          }
          onStartTesterSession={(study, task) =>
            setScreen({ name: "start-session", token: screen.token, study, task })
          }
        />
      );
      break;
    case "defined-path":
      content = (
        <DefinedPathCaptureScreen
          token={screen.token}
          study={screen.study}
          task={screen.task}
          onDone={() => setScreen({ name: "done", message: "Defined journey saved." })}
        />
      );
      break;
    case "start-session":
      content = (
        <StartTesterSessionScreen
          token={screen.token}
          study={screen.study}
          task={screen.task}
          onHandOffToTester={(params) => setScreen({ name: "tester-capture", ...params })}
        />
      );
      break;
    case "tester-entry":
      content = (
        <TesterEntryScreen
          onEnter={(params) => setScreen({ name: "tester-capture", ...params })}
          onCancel={() => setScreen({ name: "home" })}
        />
      );
      break;
    case "tester-capture":
      content = (
        <TesterCaptureScreen
          captureToken={screen.captureToken}
          participantRunId={screen.participantRunId}
          figmaUrl={screen.figmaUrl}
          instruction={screen.instruction}
          onFinished={() => setScreen({ name: "done", message: "Thanks — your session was recorded." })}
        />
      );
      break;
    case "done":
      content = <DoneScreen message={screen.message} onRestart={() => setScreen({ name: "home" })} />;
      break;
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="dark-content" />
      {content}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: "#fff" },
});
