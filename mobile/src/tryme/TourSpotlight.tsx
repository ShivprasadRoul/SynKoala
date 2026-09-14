import { useState, type ReactNode } from "react";
import { ActivityIndicator, StyleSheet, Text, TouchableOpacity, View, type LayoutChangeEvent } from "react-native";

const RING_COLOR = "#22c55e";
const DIM_COLOR = "rgba(15,23,32,0.6)";
const PAD = 8;

type Rect = { x: number; y: number; width: number; height: number };

// React Native has no CSS box-shadow spread trick, so the "everything but
// this region is dimmed" effect is built from four opaque bands (top,
// bottom, left, right of the measured target) plus a bordered ring drawn
// exactly over it — all absolutely positioned within the same container the
// content itself lays out in, so `onLayout`'s parent-relative x/y is already
// the right coordinate space (no window-measure/SafeArea math needed).
export function SpotlightRegion({ children }: { children: ReactNode }) {
  const [rect, setRect] = useState<Rect | null>(null);

  function onLayout(e: LayoutChangeEvent) {
    const { x, y, width, height } = e.nativeEvent.layout;
    setRect({ x, y, width, height });
  }

  return (
    <View style={styles.container}>
      {/* flex:1 is required here (unlike on react-native-web, where a plain
          View/div happily stretches to fit): without it this wrapper has no
          intrinsic size to give a flexible ScrollView child, so it collapses
          to zero height and the real screen content never appears. */}
      <View style={styles.contentWrapper} onLayout={onLayout}>
        {children}
      </View>
      {rect && (
        <View style={StyleSheet.absoluteFill} pointerEvents="none">
          <View
            style={[
              styles.dim,
              { top: 0, left: 0, right: 0, height: Math.max(0, rect.y - PAD) },
            ]}
          />
          <View
            style={[
              styles.dim,
              { top: rect.y + rect.height + PAD, left: 0, right: 0, bottom: 0 },
            ]}
          />
          <View
            style={[
              styles.dim,
              {
                top: Math.max(0, rect.y - PAD),
                left: 0,
                width: Math.max(0, rect.x - PAD),
                height: rect.height + PAD * 2,
              },
            ]}
          />
          <View
            style={[
              styles.dim,
              {
                top: Math.max(0, rect.y - PAD),
                left: rect.x + rect.width + PAD,
                right: 0,
                height: rect.height + PAD * 2,
              },
            ]}
          />
          <View
            style={[
              styles.ring,
              {
                top: Math.max(0, rect.y - PAD),
                left: Math.max(0, rect.x - PAD),
                width: rect.width + PAD * 2,
                height: rect.height + PAD * 2,
              },
            ]}
          />
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  contentWrapper: { flex: 1 },
  dim: { position: "absolute", backgroundColor: DIM_COLOR },
  ring: {
    position: "absolute",
    borderWidth: 2.5,
    borderColor: RING_COLOR,
    borderRadius: 18,
  },
});

export function TourTooltip({
  eyebrow,
  title,
  description,
  progressLabel,
  onBack,
  onNext,
  nextLabel = "Next →",
  hideNext = false,
  hideBack = false,
  nextLoading = false,
}: {
  eyebrow: string;
  title: string;
  description: string;
  progressLabel: string;
  onBack: () => void;
  onNext: () => void;
  nextLabel?: string;
  hideNext?: boolean;
  hideBack?: boolean;
  nextLoading?: boolean;
}) {
  return (
    <View style={tooltipStyles.wrap} pointerEvents="box-none">
      <View style={tooltipStyles.card}>
        <View style={tooltipStyles.headerRow}>
          <View style={tooltipStyles.eyebrowPill}>
            <Text style={tooltipStyles.eyebrowText}>{eyebrow}</Text>
          </View>
          <Text style={tooltipStyles.progress}>{progressLabel}</Text>
        </View>
        <Text style={tooltipStyles.title}>{title}</Text>
        <Text style={tooltipStyles.description}>{description}</Text>
        <View style={tooltipStyles.controlsRow}>
          <TouchableOpacity onPress={onBack} disabled={hideBack} hitSlop={8}>
            <Text style={[tooltipStyles.backText, hideBack && tooltipStyles.hidden]}>← Back</Text>
          </TouchableOpacity>
          {!hideNext && (
            <TouchableOpacity style={tooltipStyles.nextButton} onPress={onNext} disabled={nextLoading}>
              {nextLoading ? (
                <ActivityIndicator color="#fff" size="small" />
              ) : (
                <Text style={tooltipStyles.nextText}>{nextLabel}</Text>
              )}
            </TouchableOpacity>
          )}
        </View>
      </View>
    </View>
  );
}

const tooltipStyles = StyleSheet.create({
  wrap: { position: "absolute", left: 16, right: 16, bottom: 24 },
  card: {
    backgroundColor: "#fff",
    borderRadius: 16,
    padding: 18,
    gap: 4,
    shadowColor: "#000",
    shadowOpacity: 0.18,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 6 },
    elevation: 8,
  },
  headerRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  eyebrowPill: {
    backgroundColor: "#e2e8f0",
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  eyebrowText: { fontSize: 10, fontWeight: "700", color: "#555", letterSpacing: 0.5 },
  progress: { fontSize: 12, color: "#888", fontVariant: ["tabular-nums"] },
  title: { fontSize: 16, fontWeight: "700", color: "#111", marginTop: 8 },
  description: { fontSize: 13, color: "#555", lineHeight: 19, marginTop: 4 },
  controlsRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: 14,
  },
  backText: { fontSize: 14, fontWeight: "600", color: "#555" },
  hidden: { opacity: 0 },
  nextButton: {
    backgroundColor: "#1d4ed8",
    borderRadius: 10,
    paddingVertical: 10,
    paddingHorizontal: 18,
  },
  nextText: { color: "#fff", fontSize: 14, fontWeight: "700" },
});
