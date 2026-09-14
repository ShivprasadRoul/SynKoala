# syntax=docker/dockerfile:1

FROM node:22-slim AS base

# --- deps: install once, reused by both the build and (implicitly) cache ----
FROM base AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# --- builder: NEXT_PUBLIC_* vars are inlined into the client bundle at build
# time, not read at runtime — they have to be real ARGs here, not just
# container env vars, or every NEXT_PUBLIC_* reference in the bundle would be
# "undefined". Defaults match the values already used by the real deployed
# backend/Supabase project; override with --build-arg if either ever moves. --
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

ARG NEXT_PUBLIC_API_BASE_URL=https://synkoala-backend-97644101518.us-central1.run.app
ARG NEXT_PUBLIC_SUPABASE_URL=https://ftbhvjdirpbbpxibqlei.supabase.co
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZ0Ymh2amRpcnBiYnB4aWJxbGVpIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODkwMTc0NTAsImV4cCI6MjEwNDU5MzQ1MH0.dCAldq8Clb9vn8thjXwjiPwHGLj31JEgGYNlPRqONuk
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_SUPABASE_URL=$NEXT_PUBLIC_SUPABASE_URL
ENV NEXT_PUBLIC_SUPABASE_ANON_KEY=$NEXT_PUBLIC_SUPABASE_ANON_KEY

RUN npm run build

# --- runtime: only the standalone server output, no build tooling ----------
FROM base AS runtime
WORKDIR /app
ENV NODE_ENV=production
# Next's standalone server binds to $HOSTNAME (defaults to localhost, which
# Cloud Run's health checks can't reach) — must be explicit.
ENV HOSTNAME=0.0.0.0

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

# Cloud Run sets $PORT (default 8080); the standalone server reads it itself.
CMD ["sh", "-c", "PORT=${PORT:-8080} node server.js"]
