"use client";
import { useRef } from "react";
import dynamic from "next/dynamic";
import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import type { Artifact, Source } from "@/lib/types";

const MapView = dynamic(() => import("./MapView"), {
  ssr: false,
  loading: () => <div className="h-72 w-full animate-pulse rounded-lg bg-black/[0.04]" />,
});

const PALETTE = ["#10644C", "#2563eb", "#b45309", "#7c3aed", "#be123c", "#0891b2"];
const color = (i: number) => PALETTE[i % PALETTE.length];

function dir(yoy?: number | null) {
  if (yoy == null) return { c: "text-stable", a: "·" };
  if (yoy > 0.5) return { c: "text-firm", a: "▲" };
  if (yoy < -0.5) return { c: "text-cool", a: "▼" };
  return { c: "text-stable", a: "▬" };
}

async function exportPng(el: HTMLElement | null, name: string) {
  if (!el) return;
  const { toPng } = await import("html-to-image");
  const url = await toPng(el, { backgroundColor: "#ffffff", pixelRatio: 2 });
  const a = document.createElement("a");
  a.href = url;
  a.download = `${name.replace(/[^a-z0-9]+/gi, "_")}.png`;
  a.click();
}

function ConfidenceBadge({ c }: { c?: string }) {
  if (!c) return null;
  const tone = c === "moderate" ? "bg-ground-soft text-ground" : "bg-amber-50 text-stable";
  return <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${tone}`}>{c}</span>;
}

function Sources({ sources }: { sources?: Source[] }) {
  if (!sources?.length) return null;
  return (
    <details className="mt-3 text-xs text-black/55">
      <summary className="cursor-pointer select-none hover:text-ground">
        Show your work · {sources.length} source{sources.length > 1 ? "s" : ""}
      </summary>
      <div className="mt-2 space-y-1">
        {sources.map((s, i) => (
          <div key={i} className="rounded bg-black/[0.03] px-2 py-1 font-mono">
            <span className="text-ground">{s.es_index || s.label}</span>
            {s.query ? ` · ${s.query}` : ""}{s.n != null ? ` · n=${s.n.toLocaleString()}` : ""}
            {s.date_range ? ` · ${s.date_range}` : ""}
          </div>
        ))}
      </div>
    </details>
  );
}

function mergeLines(a: Artifact) {
  const map = new Map<string, any>();
  (a.lines || []).forEach((ln) =>
    ln.points.forEach((p) => {
      const row = map.get(p.date) || { date: p.date };
      row[ln.metro_id] = p.value;
      map.set(p.date, row);
    })
  );
  return Array.from(map.values()).sort((x, y) => (x.date < y.date ? -1 : 1));
}

function Body({ a }: { a: Artifact }) {
  if (a.type === "metric_cards") {
    return (
      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
        {(a.cards || []).map((c, i) => {
          const d = dir(c.yoy_pct);
          return (
            <div key={i} className="rounded-lg bg-ground-soft/60 p-3">
              <div className="text-xs text-black/55">{c.label}</div>
              <div className="mt-1 text-xl font-semibold tabular-nums">
                {typeof c.latest === "number" ? c.latest.toLocaleString() : c.latest}
              </div>
              <div className={`text-sm ${d.c}`}>{d.a} {c.yoy_pct != null ? `${c.yoy_pct}% YoY` : "—"}</div>
              <div className="text-[10px] text-black/40">as of {c.as_of}</div>
            </div>
          );
        })}
      </div>
    );
  }
  if (a.type === "timeseries") {
    const data = mergeLines(a);
    const keys = (a.lines || []).map((l) => l.metro_id);
    const lead = a.annotations?.[0]?.lead_months;
    return (
      <div className="mt-2">
        {lead != null && (
          <div className="mb-1 text-xs text-ground">estimated lead: ~{lead} months (corr {a.annotations?.[0]?.corr})</div>
        )}
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={data} margin={{ top: 6, right: 12, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#00000010" />
            <XAxis dataKey="date" tick={{ fontSize: 10 }} minTickGap={40} />
            <YAxis tick={{ fontSize: 10 }} width={48} />
            <Tooltip contentStyle={{ fontSize: 12 }} />
            {keys.length > 1 && <Legend wrapperStyle={{ fontSize: 11 }} />}
            {keys.map((k, i) => (
              <Line key={k} type="monotone" dataKey={k} stroke={color(i)} dot={false} strokeWidth={2} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  }
  if (a.type === "bar") {
    return (
      <div className="mt-2">
        <ResponsiveContainer width="100%" height={Math.max(160, (a.bars?.length || 1) * 30)}>
          <BarChart data={a.bars} layout="vertical" margin={{ left: 10, right: 16 }}>
            <XAxis type="number" tick={{ fontSize: 10 }} />
            <YAxis type="category" dataKey="metro_id" tick={{ fontSize: 11 }} width={120} />
            <Tooltip contentStyle={{ fontSize: 12 }} />
            <Bar dataKey="value" fill="#10644C" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }
  if (a.type === "map") {
    const hasCoords = (a.regions || []).some((r) => r.lat != null && r.lng != null);
    if (hasCoords) return <div className="mt-2"><MapView regions={a.regions as any} /></div>;
    const regions = (a.regions || []).filter((r) => r.value != null).sort((x, y) => y.value - x.value);
    const max = Math.max(...regions.map((r) => r.value), 1);
    return (
      <div className="mt-2 max-h-64 space-y-1 overflow-auto scroll-thin pr-1">
        {regions.slice(0, 60).map((r, i) => (
          <div key={i} className="flex items-center gap-2 text-xs">
            <div className="w-28 shrink-0 truncate text-black/60">{r.region}</div>
            <div className="h-3 flex-1 rounded bg-black/[0.04]">
              <div className="h-3 rounded bg-ground" style={{ width: `${(r.value / max) * 100}%` }} />
            </div>
            <div className="w-20 shrink-0 text-right tabular-nums">{Math.round(r.value).toLocaleString()}</div>
          </div>
        ))}
      </div>
    );
  }
  if (a.type === "table") {
    const cols = a.columns || [];
    return (
      <div className="mt-2">
        {a.summary_text && <div className="mb-1 text-xs text-black/55">{a.summary_text}</div>}
        <div className="max-h-72 overflow-auto scroll-thin rounded border border-black/[0.05]">
          <table className="w-full text-left text-xs">
            <thead className="sticky top-0 bg-ground-soft">
              <tr>{cols.map((c) => <th key={c} className="px-2 py-1 font-medium">{c}</th>)}</tr>
            </thead>
            <tbody>
              {(a.rows || []).map((row, i) => (
                <tr key={i} className="border-t border-black/[0.04]">
                  {cols.map((c) => <td key={c} className="px-2 py-1 align-top">{String(row[c] ?? "")}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }
  return null;
}

export default function ArtifactCard({ artifact }: { artifact: Artifact }) {
  const ref = useRef<HTMLDivElement>(null);
  return (
    <div ref={ref} className="rounded-xl border border-black/[0.06] bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-ground-ink">{artifact.title}</span>
          <ConfidenceBadge c={artifact.confidence} />
        </div>
        <button
          onClick={() => exportPng(ref.current, artifact.title)}
          className="shrink-0 rounded-md border border-black/10 px-2 py-0.5 text-[11px] text-black/45 hover:border-ground hover:text-ground"
          title="Export as PNG for your IC memo"
        >
          ↧ PNG
        </button>
      </div>
      <Body a={artifact} />
      <Sources sources={artifact.sources} />
    </div>
  );
}
