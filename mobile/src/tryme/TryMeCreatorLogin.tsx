import { useState } from "react";
import { View } from "react-native";
import { Button, FakeInput, Heading, Hint } from "./ui";
import { DEMO_CREDENTIALS } from "./data";

export function TryMeCreatorLogin({ onAdvance }: { onAdvance: () => void }) {
  const [loading, setLoading] = useState(false);

  function signIn() {
    setLoading(true);
    setTimeout(() => {
      setLoading(false);
      onAdvance();
    }, 500);
  }

  return (
    <View style={{ gap: 12 }}>
      <Heading>Creator sign-in</Heading>
      <Hint>Same account as the research dashboard (Supabase auth).</Hint>
      <FakeInput label="Email" value={DEMO_CREDENTIALS.email} />
      <FakeInput label="Password" value={DEMO_CREDENTIALS.password} secure />
      <Button label="Sign in" onPress={signIn} loading={loading} />
    </View>
  );
}
