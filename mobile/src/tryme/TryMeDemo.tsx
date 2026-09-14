import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { SpotlightRegion, TourTooltip } from "./TourSpotlight";
import { TryMeIntro } from "./TryMeIntro";
import { TryMeCreatorLogin } from "./TryMeCreatorLogin";
import { TryMeCreatorPicker } from "./TryMeCreatorPicker";
import { TryMeDefinedPath } from "./TryMeDefinedPath";
import { TryMeTesterEntry } from "./TryMeTesterEntry";
import { TryMeTesterCapture } from "./TryMeTesterCapture";
import { TryMeDone } from "./TryMeDone";
import { useState } from "react";

type Track = "creator" | "tester";

// hideNext: screens with their own multi-phase primary action (start
// walkthrough -> capture -> finish) drive advancement themselves, same
// convention as the web /try-me's Simulation step — a redundant tooltip
// "Next" there would either do nothing useful or skip the animation.
const CREATOR_COPY = [
  {
    title: "Signing in as the study creator",
    description:
      "Creators use the same Supabase account as the research dashboard — one login, both surfaces.",
    hideNext: false,
  },
  {
    title: "Pick a study and task",
    description: "Only studies marked READY in the web dashboard can record a defined path here.",
    hideNext: false,
  },
  {
    title: "Recording the defined journey",
    description:
      "A one-time walkthrough of the intended path — buffered locally and submitted as one call at the end, not streamed live.",
    hideNext: true,
  },
];

// Index 0 (the entry screen) is never actually read for its copy — that step
// renders plain, with no guided-tour overlay at all (see the track === "tester"
// && step === 0 branch below). Kept as a slot rather than restructuring the
// array so the tester track's total step count / progress math stays simple.
const TESTER_COPY = [
  {
    title: "A tester's capture token",
    description:
      "In the real app the creator hands off a capture token, run id, Figma link, and instruction together, out of band — simplified here to one field, since what matters for this tour is the emulated prototype next.",
    hideNext: false,
  },
  {
    title: "Capturing a blind attempt",
    description:
      "This is the actual prototype the tester attempts the task on — in the real app, every tap here posts to the backend immediately as it happens.",
    hideNext: true,
  },
];

export function TryMeDemo({ onExit }: { onExit: () => void }) {
  const [track, setTrack] = useState<Track | null>(null);
  const [step, setStep] = useState(0);
  const [finished, setFinished] = useState(false);

  function pickTrack(t: Track) {
    setTrack(t);
    setStep(0);
    setFinished(false);
  }

  function restart() {
    setTrack(null);
    setStep(0);
    setFinished(false);
  }

  function advance() {
    const total = track === "creator" ? CREATOR_COPY.length : TESTER_COPY.length;
    if (step + 1 >= total) {
      setFinished(true);
    } else {
      setStep((s) => s + 1);
    }
  }

  function back() {
    if (step === 0) {
      setTrack(null);
    } else {
      setStep((s) => s - 1);
    }
  }

  if (!track) {
    return <TryMeIntro onPickTrack={pickTrack} onExit={onExit} />;
  }

  if (finished) {
    return (
      <TryMeDone
        message={
          track === "creator"
            ? "Defined journey saved. Simulation started for 50 participants."
            : "Thanks — your session was recorded."
        }
        onRestart={restart}
        onExit={onExit}
      />
    );
  }

  // The tester track's entry screen (level-1 landing right after "I have a
  // tester code") is a single static field and one button — plain, with no
  // guided-tour overlay, unlike every other step. The overlay stays on the
  // capture screen after it, where there's an actual emulated prototype to
  // narrate.
  if (track === "tester" && step === 0) {
    return (
      <View style={styles.root}>
        <View style={styles.topBar}>
          <TouchableOpacity onPress={() => setTrack(null)} hitSlop={8}>
            <Text style={styles.exitLink}>← Back</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={onExit} hitSlop={8}>
            <Text style={styles.exitLink}>Exit</Text>
          </TouchableOpacity>
        </View>
        <ScrollView style={styles.scroll} contentContainerStyle={styles.plainScreenPadding}>
          <TryMeTesterEntry onAdvance={advance} />
        </ScrollView>
      </View>
    );
  }

  const copyList = track === "creator" ? CREATOR_COPY : TESTER_COPY;
  const copy = copyList[step];
  const total = copyList.length;

  const creatorScreens = [
    <TryMeCreatorLogin key="0" onAdvance={advance} />,
    <TryMeCreatorPicker key="1" onAdvance={advance} />,
    <TryMeDefinedPath key="2" onAdvance={advance} />,
  ];
  const testerScreens = [
    <TryMeTesterEntry key="0" onAdvance={advance} />,
    <TryMeTesterCapture key="1" onAdvance={advance} />,
  ];
  const screen = (track === "creator" ? creatorScreens : testerScreens)[step];

  return (
    <View style={styles.root}>
      <View style={styles.topBar}>
        <Text style={styles.topBarTitle}>SynKoala — Demo</Text>
        <TouchableOpacity onPress={onExit} hitSlop={8}>
          <Text style={styles.exitLink}>Exit</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.content}>
        <SpotlightRegion>
          <ScrollView style={styles.scroll} contentContainerStyle={styles.screenPadding}>
            {screen}
          </ScrollView>
        </SpotlightRegion>
      </View>

      <TourTooltip
        eyebrow="Guided tour"
        title={copy.title}
        description={copy.description}
        progressLabel={`${step + 1} / ${total}`}
        onBack={back}
        onNext={advance}
        hideNext={copy.hideNext}
        nextLabel={step + 1 === total ? "Finish →" : "Next →"}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#fff" },
  topBar: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: "#eee",
  },
  topBarTitle: { fontWeight: "700", fontSize: 14 },
  exitLink: { color: "#1d4ed8", fontWeight: "600" },
  content: { flex: 1 },
  scroll: { flex: 1 },
  screenPadding: { padding: 20, paddingBottom: 180 },
  plainScreenPadding: { padding: 20 },
});
