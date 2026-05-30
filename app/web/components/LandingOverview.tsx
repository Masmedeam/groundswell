"use client";
import { useState } from "react";
import MetroCard from "./MetroCard";
import type { MetroOverview } from "@/lib/engine-overview";

function questionForState(state: string, metro: string): string {
  if (state === "firming") return `Why is ${metro} firming?`;
  if (state === "softening") return `Why is ${metro} softening?`;
  return `What's driving the market in ${metro}?`;
}

const CROSS_METRO_EXAMPLES = [
  "What is the engine's detection hit rate?",
  "Compare concession share across the Sun Belt",
  "Can I trade on these signals?",
];

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
  return (
    <main className="mx-auto min-h-screen max-w-7xl px-6 py-8">
      {/* Title block */}
      <div className="mb-6 text-center">
        <h1 className="text-3xl font-semibold tracking-tight text-ground-ink">
          Home<span className="text-ground">Star</span>
        </h1>
        <p className="mt-2 text-sm text-black/55">
          Rental-market intelligence — 17 markets, demand-side engine
        </p>
      </div>

      {/* Header banner — regime-dependent framing */}
      <div className="mb-5 rounded-xl border border-ground-soft bg-ground-soft/40 px-5 py-4">
        <div className="mb-1 text-sm font-semibold text-ground">
          17 markets. 6 demand signals. Different dominants per metro.
        </div>
        <p className="text-[13px] leading-relaxed text-black/65">
          The engine validates per-market:{" "}
          <strong className="text-ground-ink">postings is the universal leader</strong>{" "}
          (clean in 16 of 17),{" "}
          <strong className="text-ground-ink">JOLTS quits</strong>{" "}
          clean in 14 of 17,{" "}
          <strong className="text-ground-ink">WARN</strong>{" "}
          is SF&apos;s depth specialty (multi-cycle, leads 7mo). Click a market below to ask the agent why — drill down to the signal that&apos;s actually driving it.
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

      {/* Section title */}
      <div className="mb-3 flex items-baseline justify-between">
        <h2 className="text-sm font-semibold text-ground-ink">
          17 markets — sorted by current concession share (Sun Belt oversupply on top)
        </h2>
        {fetchedAt && (
          <span className="text-[11px] tabular-nums text-black/40">
            concessions as of {fetchedAt.slice(0, 10)}
          </span>
        )}
      </div>

      {/* Metro grid — decision 1: concession share desc */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
        {overview.map((row) => (
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
