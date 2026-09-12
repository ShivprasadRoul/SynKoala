# SynKoala Studio (Web App)

Next.js + React + TypeScript research dashboard (`planning/12-web-app.md`, HLD §3.A) — a
separate codebase from the FastAPI backend at the repo root, talking to it over plain HTTP.
Covers the core PRD §5 flow: sign in → create a study → define an audience and generate its
population → define the Critical User Task → upload a stimulus → mark the study READY → start a
simulation run → basic results.

Deferred from this pass (real endpoints, just not built against yet — see `planning/12` §7/§9):
heatmap/paths/segments/validation/insights views, the SSE live-progress stream. The results page
polls run status instead and shows the task-success/friction/discoverability metrics grid.

## Setup

```bash
cd web
npm install
cp .env.example .env.local   # fill in NEXT_PUBLIC_API_BASE_URL / NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY
npm run dev
```

`NEXT_PUBLIC_API_BASE_URL` should point at a running instance of this repo's backend
(`uv run uvicorn app.main:app --reload` from the repo root — CORS for `http://localhost:3000` is
already enabled server-side, `app/core/settings.py:cors_allowed_origins`).
`NEXT_PUBLIC_SUPABASE_ANON_KEY` is the project's anon/public key (Supabase dashboard → Project
Settings → API) — not the backend's service-role key, which must never reach the browser.

## Design system

Visual identity (colors, type, radius) is ported verbatim from
`~/Desktop/SynKoala-Landing`'s shipped Tailwind v4 `@theme` block
(`src/app/globals.css` here ↔ `app/src/index.css` there) — a warm light "paper" palette, one
lime accent used sparingly (primary actions only), near-zero corner radius, and JetBrains Mono
reserved for numeric data (`tabular-nums`). That repo's `DesignSystem/design.md` describes an
older, unshipped dark theme — the CSS actually shipped there is the source of truth, not that
doc. Fonts are self-hosted via `@fontsource/*` (Inter for body/UI, Archivo for headings,
JetBrains Mono for numbers), matching the landing repo's approach.

## Architecture

- `src/lib/apiClient.ts` — fetch wrapper attaching the current Supabase session's access token,
  parsing the backend's `{error:{code,message,details}}` envelope, retrying once after a
  session refresh on a 401.
- `src/lib/api/*.ts` — one typed module per backend resource (studies, audiences, tasks,
  stimulus, simulations), thin functions over `apiClient` — request/response shapes come from
  `planning/12-web-app.md` §5, not re-derived.
- `src/providers/AuthProvider.tsx` — Supabase session context; `src/components/AuthGuard.tsx`
  redirects to `/login` when signed out.
- `src/app/(app)/` — the authenticated shell (top nav + sign-out) wrapping `/dashboard` and
  `/studies/...`; `src/app/(app)/studies/[id]/layout.tsx` fetches the study once and renders the
  Overview/Audience/Task/Stimulus/Simulation sub-nav (`src/components/StudyTabs.tsx` — plain
  routed links with `aria-current`, not an ARIA tablist, since each "tab" is a real route).
- `src/components/ui/` — `Button`/`Card`/`Input`/`StatusBadge` built directly on the design
  tokens, no component library (matching the landing repo's own approach).

## Known gap

There's no backend endpoint to list past simulation runs for a study (only
create/detail/cancel/progress by run id) — so the Simulation tab can only link to the run it
just started, not browse history. Flagged in `planning/12-web-app.md`'s integration notes; would
need a small backend addition later.
