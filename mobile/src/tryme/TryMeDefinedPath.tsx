import { useEffect, useState } from "react";
import { View } from "react-native";
import { Button, FakeInput, Heading, Hint, StepList } from "./ui";
import { JOURNEY_STEPS } from "./data";

export function TryMeDefinedPath({ onAdvance }: { onAdvance: () => void }) {
  const [phase, setPhase] = useState<"setup" | "capturing" | "submitting">("setup");
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (phase !== "capturing" || count >= JOURNEY_STEPS.length) return;
    const timer = setTimeout(() => setCount((c) => c + 1), 450);
    return () => clearTimeout(timer);
  }, [phase, count]);

  if (phase === "setup") {
    return (
      <View style={{ gap: 12 }}>
        <Heading>Paste the Figma prototype link</Heading>
        <Hint>The architect reads the whole prototype before this walkthrough begins.</Hint>
        <FakeInput label="Prototype URL" value="figma.com/proto/demo/Signup-Login-Flow" />
        <Button label="Start walkthrough" onPress={() => setPhase("capturing")} />
      </View>
    );
  }

  const finished = count >= JOURNEY_STEPS.length;

  return (
    <View style={{ gap: 12 }}>
      <Heading>Recording your walkthrough</Heading>
      <Hint>Tap through the prototype the same way a participant would — every step is buffered locally.</Hint>
      <StepList steps={JOURNEY_STEPS} activeCount={count} />
      <Hint>{count} step(s) recorded</Hint>
      <Button
        label="Finish & submit"
        disabled={!finished}
        loading={phase === "submitting"}
        onPress={() => {
          setPhase("submitting");
          setTimeout(onAdvance, 600);
        }}
      />
    </View>
  );
}
