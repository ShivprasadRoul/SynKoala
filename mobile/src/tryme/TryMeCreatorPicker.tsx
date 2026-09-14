import { View } from "react-native";
import { Button, Card, Heading, Hint } from "./ui";
import { DEMO_STUDY, DEMO_TASK } from "./data";

export function TryMeCreatorPicker({ onAdvance }: { onAdvance: () => void }) {
  return (
    <View style={{ gap: 12 }}>
      <Heading>{DEMO_TASK.instruction}</Heading>
      <Card>
        <Hint>Study</Hint>
        <Heading>{DEMO_STUDY.name}</Heading>
        <Hint>
          {DEMO_STUDY.populationSize} synthetic participants · {DEMO_STUDY.status}
        </Hint>
      </Card>
      <Button label="Record defined path" onPress={onAdvance} />
      <Hint>
        This same screen can also start a session for a recruited human tester — that's the
        other half of this tour.
      </Hint>
    </View>
  );
}
