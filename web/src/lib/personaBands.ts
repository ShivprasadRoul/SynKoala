// Mirrors app/services/audience_engine.py's own band thresholds — a displayed
// "Medium" always means the same 0.0-1.0 range the backend samples from.
export function bandLabel(value: number): "Low" | "Medium" | "High" {
  if (value < 0.4) return "Low";
  if (value < 0.65) return "Medium";
  return "High";
}
