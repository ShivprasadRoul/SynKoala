# Figma setup

Two independent Figma integrations in this repo need their own credentials from the same
Figma app, for two unrelated reasons:

- **OAuth** (backend, §1-4 below) — lets the Stimulus Engine's Figma import
  (`planning/05-stimulus-engine.md`) fetch a prototype file's structure on a researcher's
  behalf. Needs `FIGMA_CLIENT_ID`/`FIGMA_CLIENT_SECRET`.
- **Embed API** (mobile app, §5 below) — lets `FigmaCaptureView` (Journey Capture,
  `planning/13-journey-capture.md`) receive real navigation events from the embedded
  prototype player a human tester interacts with. Needs a separate Embed API client id.

Both live under the same Figma app (one app, `figma.com/developers/apps`), but they're
different credentials with different setup steps — don't confuse them.

## 1. Create the Figma OAuth app

This is a **one-time setup per deployment** — one app, one
`FIGMA_CLIENT_ID`/`FIGMA_CLIENT_SECRET` pair — not per researcher. Each researcher then
connects their *own* account separately (step 3 below).

1. Go to [figma.com/developers/apps](https://www.figma.com/developers/apps) (or click
   "My Apps" from the Figma toolbar).
2. Click **Create a new app** (top-right), give it a name, pick a team/organization, then
   **Create**.
3. A configuration modal shows the **Client ID** and **Client Secret** — copy both now.
   The secret is shown once; if you lose it, regenerate it from the **OAuth credentials**
   page later.
4. On the **OAuth credentials** page, click **Add a redirect URL** and add exactly the
   value you'll use for `FIGMA_REDIRECT_URI` below. Figma rejects a token exchange whose
   `redirect_uri` doesn't match one registered here character-for-character:
   - Local dev: `http://localhost:8000/api/v1/auth/figma/callback`
   - Deployed: `https://<your-backend-host>/api/v1/auth/figma/callback`
5. On the **OAuth scopes** page, make sure **`file_content:read`** is available/enabled
   for the app. `app/services/figma_oauth_service.py`'s `FIGMA_OAUTH_SCOPE` already
   requests exactly this scope automatically — nothing to configure in this app's code,
   just don't restrict the app to fewer scopes than that on Figma's side.
6. Leave the app in **draft** while developing — draft apps can be authorized by you and
   your team's plan admins, enough to test the connect flow end-to-end. Publishing (so any
   Figma user can authorize it) requires Figma's review and isn't needed for internal use.

## 2. Set the backend's environment variables

Add to `.env` (see `.env.example`):

```
FIGMA_CLIENT_ID=<the Client ID from step 1>
FIGMA_CLIENT_SECRET=<the Client Secret from step 1>
FIGMA_REDIRECT_URI=<the exact redirect URL you registered in step 1>
FIGMA_TOKEN_ENCRYPTION_KEY=<generate with the command below>
```

`FIGMA_TOKEN_ENCRYPTION_KEY` encrypts each researcher's Figma access/refresh tokens at
rest in the `figma_connections` table — it's unrelated to the OAuth client secret above,
and specific to this backend, not something Figma gives you:

```
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Restart the backend after setting these. `FigmaOAuthService.require_configured()` returns
a `503` on the connect/callback routes until all three of `FIGMA_CLIENT_ID`/
`FIGMA_CLIENT_SECRET`/`FIGMA_REDIRECT_URI` are set — `FIGMA_TOKEN_ENCRYPTION_KEY` isn't
checked there but is required the moment a token actually needs encrypting/decrypting.

## 3. Connect a researcher's Figma account

Each researcher connects their own account once, from the web app's Stimulus page
("Connect Figma account" button). This is a per-user link (`figma_connections`, one row
per `user_id`), separate from the one app-level `FIGMA_CLIENT_ID`/`FIGMA_CLIENT_SECRET`
above:

1. The button calls `GET /api/v1/auth/figma/authorize` (with the researcher's Supabase
   session), which returns `{"authorize_url": ...}` rather than redirecting directly —
   that route needs the caller's Bearer token, which only an authenticated fetch can
   attach, so the frontend does the actual top-level browser redirect itself.
2. The browser navigates to that URL — Figma's own consent screen.
3. On approval, Figma redirects to `FIGMA_REDIRECT_URI`
   (`GET /api/v1/auth/figma/callback`), which exchanges the code for an access + refresh
   token and stores them (encrypted) against that researcher's account.

## 4. What the connected account needs, per file

Importing a specific Figma file (`POST /studies/:id/stimulus` with `type=figma` and the
prototype URL, then `POST /studies/:id/stimulus/analyze`) still needs the *connected
account* to be able to view that file — owns it, has been shared it, or it's set to
"Anyone with the link can view." A file the connected account can't open fails the import
job with a clear error, not a silent empty import.

## 5. Enable the Embed API for the mobile Journey Capture app

`mobile/src/components/FigmaCaptureView.tsx` embeds Figma's prototype player in a WebView
so a human tester can walk through it. Without this section's setup, that embed only ever
sends bare pass-through `postMessage`s — Figma silently withholds the richer navigation
events (`PRESENTED_NODE_CHANGED`) unless the embed is authenticated with a client id *and*
loaded from an origin that app has explicitly allowlisted.

1. In the same Figma app from §1 (`figma.com/developers/apps` → your app), open the
   **Embed API** section. It shows its own **Client ID** — distinct from the OAuth
   Client ID in §1; this one is meant to sit in a public embed URL, so it's fine to ship
   it in the mobile app's bundled config, unlike the OAuth Client Secret.
2. Under **Allowed embed origins**, add exactly:
   ```
   https://synkoala.app
   ```
   This has to match `FIGMA_EMBED_BASE_URL` in
   `mobile/src/components/FigmaCaptureView.tsx` character-for-character. It's a label,
   not a real served domain — `react-native-webview`'s `baseUrl` is what makes the
   WebView's inline HTML present as being loaded from this origin at all (an Android/iOS
   WebView otherwise gives inline HTML no origin Figma could allowlist). If you'd rather
   use a domain you actually control, change both this Figma setting and
   `FIGMA_EMBED_BASE_URL` together — they must always match.
3. Set `EXPO_PUBLIC_FIGMA_EMBED_CLIENT_ID` in `mobile/.env` (see `mobile/.env.example`) to
   the Embed API Client ID from step 1, then rebuild/restart the Expo app — Expo inlines
   `EXPO_PUBLIC_*` vars at build time, so an already-running dev server won't pick up a
   change without a restart.
4. This is unverified against a live device as of this writing (no way to run a mobile
   WebView from this environment) — confirm the richer events actually arrive via
   `adb logcat | grep ReactNativeJS` before relying on automatic capture over the manual
   Log Tap/Scroll/Back fallback.
