# Synthetic Koala — Hackathon Pitch Script

*Format: storyline + slide-by-slide script, not a designed deck. Build the actual slides from this. Target: ~5 min pitch + demo.*

---

## The Wow Factor (lead with this, one sentence)

> **We don't ask an AI to guess what a heatmap might look like. We run a population of hundreds of distinct synthetic users through your actual UI, one decision at a time, and then we prove — against a real human who tried the same task — that the population's behavior actually matches.**

Three things nobody else in "AI UX testing" is doing together:
1. **Population, not persona.** Not "ask GPT to pretend to be a user." A sampled *distribution* of synthetic participants with individually varying traits, each running an independent perceive→attend→decide→act loop.
2. **Evidence before insight.** No insight is allowed to exist unless it cites a real, persisted metric. If the number doesn't check out against the database, the insight is silently dropped — never "smoothed over" by re-prompting the model.
3. **It grades its own homework.** A human tester walks the same prototype cold, through the same capture app. We compare the synthetic population's discovered path against that real human's path — so we're not just generating pretty heatmaps, we're reporting *how much you should trust them.*

That third point is the one nobody expects. Everyone can demo a heatmap. Nobody else in the room will show you a number that says "our synthetic population agreed with a real human 84% of the time" — and means it, because it's computed, not claimed.

---

## Slide 1 — Cold Open / Hook

**[Visual: a UI screenshot, greyed out, with a single question mark over it]**

**Script:**
"Before you ship a checkout flow, a signup form, a new nav — you have questions. Will people know where to click? Will they get lost? Will they actually complete the task, or quietly give up and leave?

Today, answering that means recruiting real users, scheduling sessions, running them, and waiting days. So most teams... just ship and find out.

We think there's a faster first step."

---

## Slide 2 — Introduce the Product

**[Visual: Synthetic Koala logo / wordmark]**

**Script:**
"This is **Synthetic Koala** — synthetic intelligence for human research. Put your prototype in front of a synthetic audience, and watch how they see it, move through it, and either complete your task or get stuck — before a single real user touches it."

**One-liner for the slide:** *Test your UI before your users do.*

---

## Slide 3 — The Core Idea (the equation)

**[Visual: the equation, large, center-slide]**

```
Audience × Task × Stimulus → Synthetic Experience → Observations → Population Behaviour → Insight
```

**Script:**
"Everything we build follows one rule: we never let a model jump straight from a screenshot to a heatmap. Every synthetic user's gaze, every click, every backtrack is logged as a real, structured event first. Only *then* do we aggregate. That's the difference between a plausible-looking demo and a measurement."

---

## Slide 4 — Meet the Synthetic Population

**[Visual: a grid of small avatar dots, varying — not 100 identical icons]**

**Script:**
"You define an audience — say, first-time digital banking users in India, age 25 to 35, low banking-app familiarity. We turn that into a statistical prior, and sample up to 100 individual synthetic participants from it. Each one has their own confidence, patience, exploration tendency, goal-directedness.

They're not 100 copies of one persona. They're a population — controlled diversity. Consistent with the audience you defined, but no two behave identically."

---

## Slide 5 — The Simulation Loop (this is the engineering wow moment)

**[Visual: the loop diagram — ORIENT → PERCEIVE → ATTEND → INTERPRET → SELECT ACTION → EXECUTE → UPDATE STATE → CHECK TASK, looping back]**

**Script:**
"Each synthetic participant runs a real agentic loop, one screen at a time: they perceive what's on screen, attention is drawn stochastically toward elements based on visual salience, task relevance, and their own trait profile — then they decide on an action, execute it, and re-evaluate whether the task is done, failed, or worth abandoning.

Stochastic — not scripted. That's what makes 100 runs produce a *distribution* of behavior instead of one deterministic path replayed 100 times."

---

## Slide 6 — From Chaos to Signal

**[Visual: split screen — left: a stream of raw event rows (GAZE, CLICK, BACKTRACK...); right: a clean heatmap + funnel]**

**Script:**
"All of that becomes an append-only observation log — every gaze, tap, scroll, backtrack. Nothing downstream is allowed to touch a screenshot directly again. Our Analytics Engine turns that log into three layers, in priority order:

- **Task success** — completion, failure, abandonment, time. The headline number.
- **Friction** — backtracks, hesitation, dead ends. *Why* success isn't higher.
- **Discoverability** — attention, click distribution, CTA discovery. *Whether* they could even find what they needed.

Heatmaps live in that third layer. They're a diagnostic, not the deliverable — the deliverable is: *did they complete the task, and why or why not.*"

---

## Slide 7 — The Differentiator: We Check Our Own Work

**[Visual: side-by-side — "Defined Journey" (creator's path, dotted line) vs "Actual Journey" (human tester, solid line) vs "Synthetic Population" (heatmap cloud of paths) converging on the same screen graph]**

**Script:**
"Here's the part that makes this defensible instead of just impressive.

The person who designed the prototype *knows* the intended path — they built it. A real user doesn't. So we capture that gap directly: the creator walks their own prototype once through a lightweight capture app — that's the **defined journey**. Then we recruit a real human tester, hand them *only the task*, never the path, and they attempt it cold through the same app — that's the **actual journey**.

Now we have three things to compare on the same footing: the defined journey, the real human's journey, and the synthetic population's journeys. We report things like *'61% of the simulated audience discovers the intended path; 39% deviate — here's how.'* And critically, we report how closely that synthetic number tracks the *real human's* number.

That's not a vibe. That's validation."

---

## Slide 8 — Insight, With Receipts

**[Visual: an insight card — a plain-English UX finding — with a small "Evidence" panel below it listing the exact metric IDs / sample sizes / segment it cites]**

**Script:**
"When we do bring in a large model, it's for exactly one job: turn structured evidence into a written insight — never to look at a screenshot and improvise. And every insight it writes gets checked, mechanically, against the real stored metrics before we ever show it to a researcher. Cite a number that doesn't match, or a segment that doesn't exist? Dropped. Not fixed, not re-prompted — dropped.

We also never say 'accuracy.' We say agreement, similarity, or error — always against a named benchmark, or we say plainly that no benchmark exists yet."

---

## Slide 9 — Live Demo

**[Visual: just says "DEMO" — this is where you drive the actual app]**

**Suggested demo script (adapt to what's actually working end-to-end today):**
1. Create a study → define an audience (e.g. "first-time digital banking users, India, 25–35") → define the Critical User Task ("Transfer ₹2,000 to a saved beneficiary").
2. Import the prototype straight from Figma (OAuth, one click — no manual screenshot wrangling).
3. Kick off a simulation run for ~50–100 synthetic participants; show progress streaming live, not a spinner.
4. Show the resulting heatmap/scanpath, the completion/friction/discoverability metrics, and a segment comparison (e.g. low vs. high digital confidence).
5. Show one insight card with its evidence citations expanded.
6. *(If the human-benchmark round is wired for this demo study)* show the defined-journey vs. actual-journey vs. synthetic-population alignment number — this is your closing beat, right before the ask.

**If the model-provider key isn't live for judges:** be upfront — "the vision extraction and insight synthesis steps need a model API key we deliberately don't fake; everything else you just watched — the population sampling, the full agentic simulation loop, the analytics, the validation math — ran for real, against a real database, with zero fabricated numbers." That honesty *is* on-brand for this product; use it.

---

## Slide 10 — Why Now / Why Us

**[Visual: three logos/icons — Supabase, LangGraph, Pydantic AI — or just three words]**

**Script:**
"This isn't a wrapper. It's a modular monolith with a real Postgres-backed job queue, LISTEN/NOTIFY realtime, a LangGraph agent loop per participant, and every model call going through a typed interface — so when a specialized small model becomes available for participant simulation, we swap it in without touching a single caller. We built for the swap we know is coming, not just the demo we're giving today."

---

## Slide 11 — The Ask / Close

**[Visual: the equation again, now with a checkmark next to each stage]**

**Script:**
"Recruiting, scheduling, and running real user research still matters — we're not pretending otherwise. What we're offering is the step *before* that: know where your UI will fail, with a population instead of a guess, and a receipt instead of a vibe.

Test your UI before your users do."

---

## Appendix — One-liners to reuse anywhere

- **Tagline:** Synthetic intelligence for human research.
- **Elevator pitch (1 sentence):** Synthetic Koala runs a statistically diverse population of synthetic users through your real prototype, logs every gaze and click as structured evidence, and validates its own output against real human testers instead of just asserting it.
- **The line that gets a reaction:** "We don't just generate insights — we're the only ones in this room who can tell you *how much to trust them*."
- **If asked "isn't this just an LLM roleplaying a user?":** "No — the LLM never touches a screenshot and improvises a heatmap. Attention and actions come from a stochastic per-participant loop over structured screen data; the only place a frontier model appears is turning already-validated metrics into a written sentence, and even that sentence gets fact-checked against the database before anyone sees it."
