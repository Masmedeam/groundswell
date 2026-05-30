// Server-only data loader for the engine landing view.
// Reads Laurie's validated JSON snapshots at data/laurie-engine/ (Path B,
// JSON-on-disk; mirrors what the agent's get_signal_validation +
// get_concessions_now tools return so the landing and the agent agree
// on every number). Used by app/page.tsx; runs in server components only.

import fs from "node:fs";
import path from "node:path";

// process.cwd() in `npm run dev` is app/web/; data/laurie-engine/ is two levels up.
const LE_DIR = path.join(process.cwd(), "..", "..", "data", "laurie-engine");

function readJson<T>(name: string): T {
  return JSON.parse(fs.readFileSync(path.join(LE_DIR, `${name}.json`), "utf8")) as T;
}

export type EngineState = "firming" | "softening" | "neutral";
export type ConcessionBand = "low" | "mid" | "high" | "unknown";

export interface DominantSignal {
  name: string;
  leadMonths: number;
  corr: number;
  n: number;
}

export interface MetroOverview {
  metro_id: string;
  display_name: string;
  tier: string;
  state: EngineState;
  score: number;
  dominant: DominantSignal | null;
  concession_share: number | null;
  concession_count: number;
  n_buildings: number;
  median_asking_rent: number | null;
  concession_band: ConcessionBand;
}

export interface OverviewResult {
  overview: MetroOverview[];
  fetchedAt: string;
}

interface MetroMapEntry {
  display_name: string;
  tier?: string;
}
interface MetroMapJson {
  metros: Record<string, MetroMapEntry>;
  name_lookups: { by_display_name: Record<string, string> };
}
interface DetectionJson {
  currentByMetro: Record<string, { state: EngineState; score: number; cleanCount: number }>;
}
interface ResultsRow {
  metro: string;
  signal: string;
  target: string;
  leadMonths: number | null;
  corr: number | null;
  nAtBestLag: number;
  flags: string[];
}
interface ListingsMetro {
  n: number;
  medianAskingRent: number | null;
  concessionShare: number | null;
  concessionsCount: number;
}
interface ListingsLiveJson {
  fetched_at: string;
  metros: Record<string, ListingsMetro | { error: string }>;
}

function getDominantSignal(results: ResultsRow[], displayName: string): DominantSignal | null {
  // Mirror lib/server-data.ts get_signal_validation: dominant = clean
  // (no flags) row with highest |corr|, target=rent.
  const metroRows = results.filter(
    (r) => r.metro === displayName && r.target === "rent",
  );
  const cleanRows = metroRows.filter(
    (r) => r.flags.length === 0 && r.corr != null && r.leadMonths != null,
  );
  cleanRows.sort((a, b) => Math.abs(b.corr ?? 0) - Math.abs(a.corr ?? 0));
  const top = cleanRows[0];
  if (!top || top.corr == null || top.leadMonths == null) return null;
  return {
    name: top.signal,
    leadMonths: top.leadMonths,
    corr: top.corr,
    n: top.nAtBestLag,
  };
}

function concessionBand(share: number | null): ConcessionBand {
  if (share == null) return "unknown";
  if (share >= 0.75) return "high";
  if (share >= 0.35) return "mid";
  return "low";
}

export function getEngineOverview(): OverviewResult {
  const map = readJson<MetroMapJson>("metro-id-map");
  const det = readJson<DetectionJson>("detection");
  const results = readJson<ResultsRow[]>("results");
  const listings = readJson<ListingsLiveJson>("listings-live");

  const rows: MetroOverview[] = Object.entries(map.metros).map(([metro_id, meta]) => {
    const displayName = meta.display_name;
    const cur = det.currentByMetro[displayName];
    const listing = listings.metros[displayName];
    const hasListing = listing && "concessionShare" in listing;
    const share = hasListing ? (listing as ListingsMetro).concessionShare : null;
    return {
      metro_id,
      display_name: displayName,
      tier: meta.tier ?? "",
      state: (cur?.state ?? "neutral") as EngineState,
      score: cur?.score ?? 0,
      dominant: getDominantSignal(results, displayName),
      concession_share: share,
      concession_count: hasListing ? (listing as ListingsMetro).concessionsCount : 0,
      n_buildings: hasListing ? (listing as ListingsMetro).n : 0,
      median_asking_rent: hasListing ? (listing as ListingsMetro).medianAskingRent : null,
      concession_band: concessionBand(share),
    };
  });

  // Decision: sort by concession share descending (Sun Belt cluster on top).
  rows.sort((a, b) => (b.concession_share ?? -1) - (a.concession_share ?? -1));

  return { overview: rows, fetchedAt: listings.fetched_at };
}
