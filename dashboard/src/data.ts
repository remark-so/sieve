export type Learning = {
  id: string;
  type: "rule" | "insight";
  learning: string;
  why: string;
  conversations: string[];
  added: string;
  updated: string;
};

export type Conversation = { date: string; conversation: string; who: string; summary: string };

export type SieveData = {
  repo: string;
  generated: string;
  lastRun: string | null;
  learnings: Learning[];
  conversations: Conversation[];
};

declare global {
  interface Window { __SIEVE__: SieveData | null }
}

// Shown only by `npm run dev`; the real page always gets data from sieve.py.
const sample: SieveData = {
  repo: "/Users/you/code/autoscience",
  generated: "2026-10-28T22:40:00",
  lastRun: "2026-10-28T22:31:41",
  learnings: [
    { id: "2281c4", type: "rule", learning: "Show an entity's human-readable title as its identity in lists and panels, and keep the internal ID only behind a copy button.", why: "A hash ID tells the user nothing and hides the title they use to recognize the item.", conversations: ["f82c95e0", "982c95e0"], added: "2026-10-13", updated: "2026-10-14" },
    { id: "af3a4b", type: "rule", learning: "Test frontend changes against a view server started before the change as well as a fresh one.", why: "Users keep old servers running, so new screens must work with them.", conversations: ["da367599"], added: "2026-10-14", updated: "2026-10-14" },
    { id: "7c01de", type: "insight", learning: "Nodes store their stage by index, so removing or reordering a stage moves every node at that position to a different stage.", why: "", conversations: ["f82c95e0"], added: "2026-10-13", updated: "2026-10-13" },
  ],
  conversations: [
    { date: "2026-10-14", conversation: "da367599", who: "Ana", summary: "Reworked the Definitions screen into a single-column document and fixed a black screen caused by an old server." },
    { date: "2026-10-13", conversation: "f82c95e0", who: "Ana", summary: "Rebuilt the browser view in React and shadcn with an editable overview and search." },
  ],
};

export const data: SieveData = window.__SIEVE__ ?? sample;
