"use client";
import type { MetroOverview } from "@/lib/engine-overview";

// Decision 3: my engine's state names rendered in Salim's visual language
// (parallels his dir() helper in Artifacts.tsx — same arrow + token mapping).
function stateDir(state: string): { c: string; a: string; label: string } {
  if (state === "firming") return { c: "text-firm", a: "▲", label: "Firming" };
  if (state === "softening") return { c: "text-cool", a: "▼", label: "Softening" };
  return { c: "text-stable", a: "▬", label: "Neutral" };
}

function bandStyle(band: string): { c: string; label: string } {
  if (band === "high") return { c: "text-cool", label: "oversupplied" };
  if (band === "low") return { c: "text-firm", label: "constrained" };
  if (band === "mid") return { c: "text-stable", label: "softening texture" };
  return { c: "text-black/40", label: "—" };
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
    <div className="rounded-xl border border-black/[0.06] bg-white p-4 shadow-sm transition hover:shadow">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-base font-semibold text-ground-ink">{row.display_name}</h3>
        <span className={`text-xs font-medium ${d.c}`}>
          {d.a} {d.label}
        </span>
      </div>
      <div className="mt-3 space-y-2 text-[12px]">
        <div>
          <div className="text-[10px] uppercase tracking-wider text-black/45">Dominant signal</div>
          {row.dominant ? (
            <div className="mt-0.5">
              <span className="font-medium text-ground-ink">{row.dominant.name}</span>
              <span className="text-black/55">
                {" "}· leads {row.dominant.leadMonths}mo · r={row.dominant.corr.toFixed(2)}
              </span>
            </div>
          ) : (
            <div className="mt-0.5 italic text-black/45">no clean signal established</div>
          )}
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-wider text-black/45">Concessions</div>
          <div className="mt-0.5">
            <span className={`font-medium ${b.c}`}>{pct}</span>
            <span className="text-black/55"> · {b.label}</span>
            {row.n_buildings > 0 && (
              <span className="ml-1 text-[11px] text-black/35">({row.n_buildings} buildings)</span>
            )}
          </div>
        </div>
      </div>
      <div className="mt-3 flex items-center gap-3 border-t border-black/[0.04] pt-2 text-[11px]">
        <button onClick={onAskWhy} className="font-medium text-ground hover:underline">
          Ask why →
        </button>
        {row.concession_share != null && (
          <button
            onClick={onAskConcessions}
            className="text-ground/70 hover:text-ground hover:underline"
          >
            Concession detail
          </button>
        )}
      </div>
    </div>
  );
}
