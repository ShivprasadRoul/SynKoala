import { StyleSheet, View } from "react-native";
import { WebView } from "react-native-webview";

interface Props {
  figmaUrl: string;
}

// A read-only preview of the real prototype, framed like a mobile mockup —
// deliberately NOT the real FigmaCaptureView: no client-id, no postMessage
// listening, no step logging, no Tap/Scroll/Back fallback controls. This is
// a demo; whatever a viewer does inside the embed itself is never captured
// or sent anywhere by this app.
export function TryMeFigmaMockup({ figmaUrl }: Props) {
  const embedUrl = `https://www.figma.com/embed?embed_host=share&url=${encodeURIComponent(figmaUrl)}`;

  return (
    <View style={styles.frame}>
      <View style={styles.notch} />
      <WebView
        source={{ uri: embedUrl }}
        style={styles.webview}
        allowsFullscreenVideo={false}
        startInLoadingState
      />
    </View>
  );
}

const styles = StyleSheet.create({
  frame: {
    height: 480,
    borderRadius: 20,
    overflow: "hidden",
    borderWidth: 6,
    borderColor: "#111",
    backgroundColor: "#000",
  },
  notch: {
    position: "absolute",
    top: 6,
    left: "50%",
    marginLeft: -30,
    width: 60,
    height: 16,
    borderBottomLeftRadius: 10,
    borderBottomRightRadius: 10,
    backgroundColor: "#111",
    zIndex: 1,
  },
  webview: { flex: 1 },
});
