"use client";
import type { MetroOverview } from "@/lib/engine-overview";

// Visual treatment: research-note entry, not dashboard card.
// - Metro name = serif headline (Source Serif 4)
// - State = quiet uppercase caption with arrow, ground / cool / stable hint
// - Numbers (lead, r-value, concession %) = tabular-nums set in body weight,
//   no loud color blocks
// - Borders/rules are 1px subtle ground tints rather than shadowed boxes
// All data and click handlers are unchanged — visual refinement only.

function stateDir(state: string): { c: string; a: string; label: string } {
  if (state === "firming") return { c: "text-firm", a: "▲", label: "Firming" };
  if (state === "softening") return { c: "text-cool", a: "▼", label: "Softening" };
  return { c: "text-stable", a: "▬", label: "Neutral" };
}

function bandStyle(band: string): { c: string; label: string } {
  if (band === "high") return { c: "text-cool", label: "oversupplied" };
  if (band === "low") return { c: "text-firm", label: "constrained" };
  if (band === "mid") return { c: "text-stable", label: "softening texture" };
  return { c: "text-ink-faint", label: "—" };
}

export default function MetroCard({
  row,
  onAskWhy,
  onAskConcessions,
}: {
  row: MetroOverview;
  onAskWhy: () => void;
  onAskConcessions: () => void;
}) {
  const d = stateDir(row.state);
  const b = bandStyle(row.concession_band);
  const pct = row.concession_share != null
    ? `${(row.concession_share * 100).toFixed(0)}%`
    : "—";
  return (
    <article className="group relative flex flex-col border-t border-rule pt-5 pb-5 px-1 transition-colors hover:border-ground/60">
      {/* Top row: metro name (serif) + state caption */}
      <header className="flex items-baseline justify-between gap-3">
        <h3 className="font-serif text-[19px] font-semibold leading-tight tracking-tight text-ground-ink">
          {row.display_name}
        </h3>
        <div className="text-right shrink-0">
          <div className={`text-[10px] font-semibold uppercase tracking-[0.14em] ${d.c}`}>
            <span className="mr-1">{d.a}</span>{d.label}
          </div>
          {row.state_since && (
            <div className="mt-0.5 text-[10px] tabular-nums text-ink-faint">
              since {row.state_since}
            </div>
          )}
        </div>
      </header>

      {/* Editorial data block — one-line captions, not labeled stat fields */}
      <dl className="mt-4 space-y-2.5 text-[12.5px] leading-relaxed">
        <div>
          <dt className="text-[9.5px] font-semibold uppercase tracking-[0.16em] text-ground/80">
            Dominant signal
          </dt>
          <dd className="mt-1 text-ink-soft">
            {row.dominant ? (
              <>
                <span className="font-medium text-ground-ink">{row.dominant.name}</span>
                <span className="tabular-nums">
                  {" "}· leads {row.dominant.leadMonths}mo · r = {row.dominant.corr.toFixed(2)}
                </span>
              </>
            ) : (
              <span className="italic text-ink-faint">no clean signal established</span>
            )}
          </dd>
        </div>
        <div>
          <dt className="text-[9.5px] font-semibold uppercase tracking-[0.16em] text-ground/80">
            Concessions
          </dt>
          <dd className="mt-1 text-ink-soft">
            <span className="font-medium tabular-nums text-ground-ink">{pct}</span>
            <span className={`ml-1 ${b.c}`}>· {b.label}</span>
            {row.n_buildings > 0 && (
              <span className="ml-1 tabular-nums text-ink-faint">
                ({row.n_buildings} buildings)
              </span>
            )}
          </dd>
        </div>
      </dl>

      {/* Affordances — kept ground green, smaller + more editorial */}
      <footer className="mt-4 flex items-center gap-4 text-[11px]">
        <button
          onClick={onAskWhy}
          className="font-medium text-ground transition hover:text-ground-deep hover:underline underline-offset-2"
        >
          Ask why →
        </button>
        {row.concession_share != null && (
          <button
            onClick={onAskConcessions}
            className="text-ink-soft transition hover:text-ground hover:underline underline-offset-2"
          >
            Concession detail
          </button>
        )}
      </footer>
    </article>
  );
}
