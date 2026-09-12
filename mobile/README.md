# SynKoala Journey Capture App

Native Android client (Expo + React Native + TypeScript) for `planning/13-journey-capture.md` /
`02-HLD-Synthetic-Koala.md` §3.A2 — a separate codebase from the FastAPI backend at the repo
root, talking to it over plain HTTP.

Two flows, both against the same backend (`app/api/v1/journey_capture.py`):

- **Creator**: signs in (Supabase auth, same account as the web dashboard), picks a study/task,
  then either records the **defined journey** (a one-time walkthrough, submitted whole at the
  end) or starts a **human tester session** (issues a short-lived capture token, no tester
  account).
- **Tester**: enters the capture token + participant-run id + Figma link handed to them by the
  creator (there is no bootstrap endpoint to fetch these from a bare token — see
  `planning/13-journey-capture.md`), then attempts the task blind, with every step posted live.

## Setup

```bash
cd mobile
npm install
cp .env.example .env   # fill in EXPO_PUBLIC_API_BASE_URL / EXPO_PUBLIC_SUPABASE_URL / EXPO_PUBLIC_SUPABASE_ANON_KEY
npx expo start --android
```

`EXPO_PUBLIC_API_BASE_URL` should point at a running instance of this repo's backend
(`uv run uvicorn app.main:app --reload --host 0.0.0.0` from the repo root — the `--host 0.0.0.0`
matters, the default only listens on `localhost`) — use your machine's LAN IP, not `localhost`,
when testing on a physical device or a non-host emulator.

That env var only sets the *default* the app ships with at build time. Once installed, the
backend address is also editable at runtime from Home → "Backend: ... (tap to change)"
(`src/screens/SettingsScreen.tsx`, persisted via `src/settings.ts`) — this is what lets one
built APK be pointed at whichever machine is running the backend, without a rebuild.

## Architecture

- `src/api/client.ts` — thin fetch wrapper (`Authorization: Bearer` for creator routes,
  `X-Capture-Token` for capture-token routes).
- `src/api/journeyCapture.ts` — one function per backend endpoint.
- `src/api/supabase.ts` — creator sign-in only (no session persistence — re-login each launch).
- `src/components/FigmaCaptureView.tsx` — embeds Figma's prototype player (Embed Kit 2.0) in a
  `WebView` and turns its `postMessage` events into captured steps, with manual Tap/Scroll/Back
  buttons as a fallback.
- `src/screens/` — one screen per step of either flow; `App.tsx` is a plain `useState` switch,
  not a navigation library — a half-dozen linear screens don't need one, and it keeps the
  toolchain to just Expo + React Native (no Android Studio/native SDK install required for
  development).

## Known risks to verify against a real device/prototype (not exercised in this environment)

- **Figma embed event shape**: `FigmaCaptureView` assumes Figma's Embed Kit 2.0 emits a
  `PRESENTED_NODE_CHANGED` message with `data.presentedNodeId` on every prototype interaction.
  Confirm this against a real Figma prototype early — if the shape differs, the manual
  Tap/Scroll/Back buttons (with a manually-entered node id) still work as a fallback.
- **`expo-audio` API**: `TesterCaptureScreen` uses `useAudioRecorder`/`RecordingPresets`/
  `AudioModule.requestRecordingPermissionsAsync` per the package's documented shape as of this
  writing — recheck against the installed version if recording doesn't work.
