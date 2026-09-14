import { View } from "react-native";
import { Button, FakeInput, Heading, Hint } from "./ui";
import { TESTER_SESSION } from "./data";

// Mirrors the shape of the creator's "paste the Figma link" screen — one
// static field, one button — rather than the real app's full session-detail
// form: this demo has nothing to actually bootstrap a capture session with,
// and the point of this flow is the emulated prototype on the next screen,
// not a realistic hand-off form.
export function TryMeTesterEntry({ onAdvance }: { onAdvance: () => void }) {
  return (
    <View style={{ gap: 12 }}>
      <Heading>Enter your session details</Heading>
      <Hint>The study creator gave you this.</Hint>
      <FakeInput label="Capture token" value={TESTER_SESSION.captureToken} />
      <Button label="Begin task" onPress={onAdvance} />
    </View>
  );
}
