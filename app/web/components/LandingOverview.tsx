"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import MetroCard from "./MetroCard";
import TopNav from "./TopNav";
import type { MetroOverview } from "@/lib/engine-overview";

// Visual treatment: editorial / research-note framing matching pitch PDF.
// - Source Serif 4 for title + section headings; Inter for body + UI
// - Cream (#FAFAF7) bg from globals.css; no shadowed boxes
// - Banner is an inline kicker + paragraph with a left ground rule
// - "Ask the analyst" is a docked popover in the upper-right (frees
//   the main column so the metro grid lands above the fold)
// All four onAsk() entry points (per-card "Ask why", per-card
// "Concession detail", popover example chip, popover free-form input)
// still call props.onAsk(), which flips messages.length 0 → 1 in
// HomeShell and transitions into the chat workspace. Agent flow and
// get_signal_validation are untouched.

function questionForState(state: string, metro: string): string {
  if (state === "firming") return `What are the top 3 signals driving the firming call in ${metro}?`;
  if (state === "softening") return `What are the top 3 signals driving the softening call in ${metro}?`;
  return `What are the top validated signals for ${metro}?`;
}

const CROSS_METRO_EXAMPLES = [
  "What is the engine's detection hit rate?",
  "Compare concession share across the Sun Belt",
  "Can I trade on these signals?",
];

type SortKey = "concessions" | "alpha" | "firmest" | "recent";

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: "concessions", label: "Concessions (high→low)" },
  { value: "alpha", label: "Alphabetical (A→Z)" },
  { value: "firmest", label: "Firmest → softest" },
  { value: "recent", label: "Confirmed turn — most recent" },
];

function sortRows(rows: MetroOverview[], key: SortKey): MetroOverview[] {
  const copy = [...rows];
  switch (key) {
    case "concessions":
      copy.sort((a, b) => (b.concession_share ?? -1) - (a.concession_share ?? -1));
      break;
    case "alpha":
      copy.sort((a, b) => a.display_name.localeCompare(b.display_name));
      break;
    case "firmest":
      copy.sort((a, b) => (b.state_score ?? 0) - (a.state_score ?? 0));
      break;
    case "recent":
      copy.sort((a, b) =>
        (b.state_since ?? "0000-00").localeCompare(a.state_since ?? "0000-00"),
      );
      break;
  }
  return copy;
}

// Docked Ask the analyst — compact button that expands to a popover.
// Submit/chip-click calls onAsk(), which flips the parent into the
// chat workspace (popover effectively goes away on transition).
// `open` state is lifted to the parent so the secondary affordance
// under the engine-status block can also trigger it.
function AskAnalystDock({
  onAsk,
  open,
  setOpen,
}: {
  onAsk: (text: string) => void;
  open: boolean;
  setOpen: (v: boolean) => void;
}) {
  const [input, setInput] = useState("");
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Click-outside + Esc to close
  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  // Autofocus input when popover opens
  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  function submit(text: string) {
    const v = text.trim();
    if (!v) return;
    setOpen(false);
    setInput("");
    onAsk(v);
  }

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className={
          "flex items-center gap-2 rounded-sm border px-3.5 py-1.5 text-[10.5px] font-semibold uppercase tracking-[0.18em] transition " +
          (open
            ? "border-ground bg-ground text-white"
            : "border-ground/70 text-ground hover:bg-ground hover:text-white")
        }
      >
        Ask the analyst
        <span className="text-[9px]">▾</span>
      </button>

      {open && (
        <div className="absolute right-0 top-[calc(100%+8px)] z-30 w-[380px] border-t-2 border-ground bg-cream shadow-[0_10px_30px_-12px_rgba(14,21,19,0.18)]">
          <div className="border-b border-rule px-5 pt-4 pb-3">
            <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-ground/80">
              Ask the analyst
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                submit(input);
              }}
              className="mt-2"
            >
              <div className="flex items-center gap-2 border-b border-rule pb-1.5 focus-within:border-ground">
                <input
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="type your question…"
                  className="flex-1 bg-transparent px-1 py-1 font-serif text-[15px] outline-none placeholder:font-sans placeholder:text-[13px] placeholder:text-ink-faint"
                />
                <button
                  type="submit"
                  className="rounded-sm bg-ground px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-white transition hover:bg-ground-deep"
                >
                  Ask
                </button>
              </div>
            </form>
          </div>
          <div className="px-5 py-4">
            <div className="text-[9.5px] font-semibold uppercase tracking-[0.18em] text-ink-faint">
              Examples
            </div>
            <ul className="mt-2 space-y-1.5">
              {CROSS_METRO_EXAMPLES.map((ex) => (
                <li key={ex}>
                  <button
                    onClick={() => submit(ex)}
                    className="text-left text-[12.5px] leading-snug text-ink-soft transition hover:text-ground hover:underline underline-offset-2"
                  >
                    · {ex}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}

export default function LandingOverview({
  overview,
  fetchedAt,
  onAsk,
}: {
  overview: MetroOverview[];
  fetchedAt: string;
  onAsk: (text: string) => void;
}) {
  const [sortKey, setSortKey] = useState<SortKey>("concessions");
  const [askOpen, setAskOpen] = useState(false);
  const sorted = useMemo(() => sortRows(overview, sortKey), [overview, sortKey]);
  return (
    <>
      <TopNav right={<AskAnalystDock onAsk={onAsk} open={askOpen} setOpen={setAskOpen} />} />
      <main className="mx-auto min-h-screen max-w-6xl px-8 pt-8 pb-16">
      {/* Title block — kicker + serif H1, since wordmark lives in TopNav now */}
      <header>
        <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-ground">
          Market overview
        </div>
        <h1 className="mt-2 font-serif text-[32px] font-semibold leading-tight tracking-tight text-ground-ink">
          17 markets across 4 tiers — the engine&apos;s current read.
        </h1>
      </header>

      {/* Editorial banner — tightened: kicker + single paragraph */}
      <section className="mt-6 grid grid-cols-[3px_1fr] gap-5">
        <div className="bg-ground/80" />
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-ground">
            Engine status
          </div>
          <p className="mt-1.5 max-w-3xl text-[13.5px] leading-relaxed text-ink-soft">
            17 markets · 6 demand signals validated · 3 tested and dropped ·
            walk-forward backtest at{" "}
            <strong className="font-semibold text-ground">79.3% hit rate</strong>.
            {" "}<strong className="font-semibold text-ground-ink">Postings</strong>{" "}
            is the universal leader (16/17),{" "}
            <strong className="font-semibold text-ground-ink">JOLTS quits</strong>{" "}
            (14/17) and{" "}
            <strong className="font-semibold text-ground-ink">WARN</strong>{" "}
            (SF&apos;s multi-cycle depth signal) corroborate underneath.
          </p>
          {/* Quiet secondary affordance — keeps the dock discoverable */}
          <button
            type="button"
            onClick={() => setAskOpen(true)}
            className="mt-2.5 text-[11.5px] text-ink-faint transition hover:text-ground"
          >
            Have a cross-metro question?{" "}
            <span className="font-medium text-ground underline underline-offset-2 decoration-ground/40 hover:decoration-ground">
              Ask the analyst
            </span>
            .
          </button>
        </div>
      </section>

      {/* Section title + sort — tighter top margin */}
      <section className="mt-7 flex items-end justify-between border-b border-rule pb-2.5">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-ground/80">
            By metro
          </div>
          <h2 className="mt-0.5 font-serif text-[18px] font-semibold leading-tight text-ground-ink">
            Click any market to ask the analyst.
          </h2>
        </div>
        <div className="flex items-center gap-5 shrink-0 pb-1">
          {fetchedAt && (
            <span className="hidden sm:inline text-[10.5px] tabular-nums uppercase tracking-[0.14em] text-ink-faint">
              concessions as of {fetchedAt.slice(0, 10)}
            </span>
          )}
          <label className="flex items-center gap-2 text-[10.5px] uppercase tracking-[0.14em] text-ink-soft">
            <span>Sort</span>
            <select
              value={sortKey}
              onChange={(e) => setSortKey(e.target.value as SortKey)}
              className="border-b border-rule bg-transparent px-1 py-0.5 text-[11.5px] normal-case tracking-normal text-ground-ink hover:border-ground focus:border-ground focus:outline-none"
            >
              {SORT_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>

      {/* Metro grid — top-rule entries, no shadowed cards */}
      <div className="grid grid-cols-1 gap-x-10 sm:grid-cols-2 lg:grid-cols-3">
        {sorted.map((row) => (
          <MetroCard
            key={row.metro_id}
            row={row}
            onAskWhy={() => onAsk(questionForState(row.state, row.display_name))}
            onAskConcessions={() => onAsk(`Tell me about ${row.display_name}'s concession picture`)}
          />
        ))}
      </div>

      <p className="mt-16 text-[10.5px] uppercase tracking-[0.18em] text-ink-faint">
        Each card click pre-seeds a question for the analyst agent. Numbers reflect the validated engine state.
      </p>
      </main>
    </>
  );
}
