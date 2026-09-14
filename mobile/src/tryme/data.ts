// Static demo data for the in-app "Try Me" walkthrough. Nothing here is
// fetched or posted anywhere — no Supabase auth, no backend calls, no Figma
// embed, no audio recording. Every value is a fixed illustrative example,
// same ethos as the web landing page's /try-me.

export const DEMO_STUDY = {
  name: "Signup & Login Flow",
  status: "READY",
  populationSize: 50,
};

export const DEMO_TASK = {
  instruction: "Able to create an account and log in",
};

export const DEMO_CREDENTIALS = {
  email: "creator@halcyonlabs.com",
  password: "••••••••••",
};

// The same illustrative screen sequence used by the web /try-me's stimulus
// step, so the two demos tell a consistent story.
export const JOURNEY_STEPS = [
  "Home",
  "Create account",
  "Email",
  "Password",
  "Continue",
  "Verify email",
  "Log in",
];

export const TESTER_SESSION = {
  // The one field the tester entry screen shows — set to the actual static
  // prototype link itself (per explicit ask), and reused as-is for the
  // embedded mobile-mockup preview on the next screen. Not a real capture
  // token — nothing here is wired to any capture/posting logic.
  captureToken:
    "https://www.figma.com/proto/pu5WkITiiJz3RIINbHxdBT/Log-in--Registration--Onboarding---Sign-in---Sign-up---Forgot-password--Community---Copy-?node-id=11-6346&starting-point-node-id=11%3A6346",
};
