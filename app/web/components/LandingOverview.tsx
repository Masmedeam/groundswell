"use client";
import { useMemo, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import MetroCard from "./MetroCard";
import type { MetroOverview } from "@/lib/engine-overview";

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
      // Sort by lastTurn.scoreAtDetection descending. Positive = firming (top);
      // negative = softening (bottom). Magnitude within each direction reflects
      // how strong the confirmed turn was, giving a real gradient.
      copy.sort((a, b) => (b.state_score ?? 0) - (a.state_score ?? 0));
      break;
    case "recent":
      // YYYY-MM strings sort lexicographically correctly.
      copy.sort((a, b) =>
        (b.state_since ?? "0000-00").localeCompare(a.state_since ?? "0000-00"),
      );
      break;
  }
  return copy;
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
  const [input, setInput] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("concessions");
  const sorted = useMemo(() => sortRows(overview, sortKey), [overview, sortKey]);
  return (
    <main className="mx-auto min-h-screen max-w-7xl px-6 py-8">
      {/* Pitch link — small, top-right, unobtrusive */}
      <div className="mb-2 flex justify-end">
        <Link
          href="/pitch"
          className="text-[11px] uppercase tracking-[0.18em] text-black/45 hover:text-ground transition"
        >
          Pitch ↗
        </Link>
      </div>

      {/* Title block — logo mark above wordmark */}
      <div className="mb-6 flex flex-col items-center text-center">
        <Image
          src="/logo.png"
          alt="HomeStar"
          width={56}
          height={56}
          priority
          className="mb-2"
        />
        <h1 className="text-3xl font-semibold tracking-tight text-ground-ink">
          Home<span className="text-ground">Star</span>
        </h1>
        <p className="mt-2 text-sm text-black/55">
          Rental-market intelligence — 17 markets, demand-side engine
        </p>
      </div>

      {/* Header banner — engine framing (postings-universal, JOLTS+WARN corroborators) */}
      <div className="mb-5 rounded-xl border border-ground-soft bg-ground-soft/40 px-5 py-4">
        <div className="mb-1 text-sm font-semibold text-ground">
          17 markets. 6 demand signals validated, 3 tested and dropped. Walk-forward backtest at 79.3% hit rate.
        </div>
        <p className="text-[13px] leading-relaxed text-black/65">
          <strong className="text-ground-ink">Postings is the universal leader</strong>{" "}
          across markets (clean in 16 of 17).{" "}
          <strong className="text-ground-ink">JOLTS quits</strong>{" "}
          (14/17) and{" "}
          <strong className="text-ground-ink">WARN</strong>{" "}
          (SF&apos;s multi-cycle depth signal) add corroborating signal underneath. Click any market to surface the full top-signal decomposition.
        </p>
      </div>

      {/* Ask anything input — moved UP under header banner (decision 4) */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const v = input.trim();
          if (v) {
            onAsk(v);
            setInput("");
          }
        }}
        className="mb-3"
      >
        <div className="flex items-center gap-2 rounded-xl border border-black/10 bg-white p-1.5 shadow-sm focus-within:border-ground">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Or ask anything cross-metro — e.g. compare Sun Belt concessions, what's the engine's hit rate"
            className="flex-1 bg-transparent px-3 py-2 text-sm outline-none placeholder:text-black/30"
          />
          <button
            type="submit"
            className="rounded-lg bg-ground px-4 py-2 text-sm font-medium text-white hover:opacity-90"
          >
            Ask
          </button>
        </div>
      </form>
      <div className="mb-7 flex flex-wrap gap-2">
        {CROSS_METRO_EXAMPLES.map((ex) => (
          <button
            key={ex}
            onClick={() => onAsk(ex)}
            className="rounded-full border border-black/10 bg-white px-3 py-1.5 text-[11px] text-black/55 hover:border-ground hover:text-ground"
          >
            {ex}
          </button>
        ))}
      </div>

      {/* Section title — sort dropdown on right (Salim's input styling — ground tokens) */}
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h2 className="text-sm font-semibold text-ground-ink">
          17 markets across 4 tiers — engine&apos;s current read per metro
        </h2>
        <div className="flex items-center gap-3 shrink-0">
          {fetchedAt && (
            <span className="hidden sm:inline text-[11px] tabular-nums text-black/40">
              concessions as of {fetchedAt.slice(0, 10)}
            </span>
          )}
          <label className="flex items-center gap-2 text-[11px] text-black/55">
            <span>Sort</span>
            <select
              value={sortKey}
              onChange={(e) => setSortKey(e.target.value as SortKey)}
              className="rounded-lg border border-black/10 bg-white px-2.5 py-1 text-[12px] text-ground-ink shadow-sm hover:border-ground focus:border-ground focus:outline-none"
            >
              {SORT_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {/* Metro grid — sorted client-side via dropdown selection */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
        {sorted.map((row) => (
          <MetroCard
            key={row.metro_id}
            row={row}
            onAskWhy={() => onAsk(questionForState(row.state, row.display_name))}
            onAskConcessions={() => onAsk(`Tell me about ${row.display_name}'s concession picture`)}
          />
        ))}
      </div>

      <p className="mt-10 text-center text-[11px] text-black/35">
        Each card click pre-seeds a question for the analyst agent. Numbers reflect the validated engine state.
      </p>
    </main>
  );
}
