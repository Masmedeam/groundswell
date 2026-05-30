// Server-only data loaders for the Data Sources + Methodology surfaces.
// Reads the same data/laurie-engine/*.json snapshots the agent reads, so
// every number on these surfaces is the same number the agent + PDF would
// emit. Pure server-component code; no client bundle.

import fs from "node:fs";
import path from "node:path";

const LE_DIR = path.join(process.cwd(), "..", "..", "data", "laurie-engine");

function readJson<T>(name: string): T {
  return JSON.parse(fs.readFileSync(path.join(LE_DIR, `${name}.json`), "utf8")) as T;
}

function statSafe(name: string): { size: number; mtime: string } | null {
  try {
    const s = fs.statSync(path.join(LE_DIR, `${name}.json`));
    return { size: s.size, mtime: s.mtime.toISOString() };
  } catch {
    return null;
  }
}

// ────────────────────────────────────────────────────────────────────
// results.json — lead-lag rows
// ────────────────────────────────────────────────────────────────────
export interface ResultsRow {
  metro: string;
  signal: string;
  target: string;
  leadMonths: number | null;
  corr: number | null;
  nAtBestLag: number;
  flags: string[];
  window?: { start: string; end: string };
  expectedSign?: number;
}
export function getResults(): ResultsRow[] {
  return readJson<ResultsRow[]>("results");
}

// ────────────────────────────────────────────────────────────────────
// detection.json — confirmed turns + per-signal-lead hits + aggregate
// ────────────────────────────────────────────────────────────────────
export interface DetectionAtSignalLead {
  n: number;
  hits: number;
  hitRate: number;
  strictHitRate?: number;
  medianDominantLead: number | null;
}
export interface DetectionGridHit {
  n: number;
  hits: number;
  hitRate: number;
}
export interface DetectionByMetroAgg {
  nTurns: number;
  hitRates: Record<string, DetectionGridHit>;
  atSignalLead?: DetectionAtSignalLead | null;
}
export interface DetectionAggregate {
  overall: {
    nTurns: number;
    nEvaluable: number;
    hitRates: Record<string, DetectionGridHit>;
    medianLeadAtFirstHit: number;
    atSignalLead: DetectionAtSignalLead;
  };
  byMetro: Record<string, DetectionByMetroAgg>;
}
export interface DetectionConfig {
  startYM: string;
  endYM: string;
  stateBuffer: number;
  persistenceMonths: number;
  pubLagMonths: number;
  horizons: number[];
  metros: string[];
  whyNotPrice?: string;
  evaluationLeadRule?: string;
}
export interface DetectionJson {
  config: DetectionConfig;
  aggregate: DetectionAggregate;
  turns: unknown[];
  currentByMetro: Record<string, unknown>;
}
export function getDetection(): DetectionJson {
  return readJson<DetectionJson>("detection");
}

// ────────────────────────────────────────────────────────────────────
// forecast-skill.json — engine vs persistence + base-rate baselines
// ────────────────────────────────────────────────────────────────────
export interface SkillBlock {
  hits: number;
  hitRate: number;
  brier: number;
  weightedAcc?: number;
}
export interface SkillJson {
  config: {
    methodology: string;
    basedOnNTurns: number;
    baseRateDirection: string;
    baseRateProb: number;
    notes?: string;
  };
  aggregate: {
    overall: {
      n: number;
      engine: SkillBlock;
      persistence: SkillBlock & { nJudged: number };
      baseRate: SkillBlock;
      skill: { vsPersistence: number; vsBaseRate: number };
      bss: { vsPersistence: number; vsBaseRate: number };
    };
  };
}
export function getSkill(): SkillJson {
  return readJson<SkillJson>("forecast-skill");
}

// ────────────────────────────────────────────────────────────────────
// backtest.json — naive 4-metro quarterly trading test
// ────────────────────────────────────────────────────────────────────
export interface BacktestJson {
  headline: {
    quarters: number;
    finalSignal: number;
    finalEqual: number;
    finalWorst: number;
    finalBenchmark: number;
    outperfVsEqualPct: number;
    outperfVsWorstPct: number;
    preStated: string;
    preStatedHeld: boolean;
  };
}
export function getBacktest(): BacktestJson {
  return readJson<BacktestJson>("backtest");
}

// ────────────────────────────────────────────────────────────────────
// backtest-rotation.json — 17-metro price-rotation test (Phase O)
// ────────────────────────────────────────────────────────────────────
export interface RotationJson {
  headline: {
    strategyMeanAnnualized: number;
    equalWeightMeanAnnualized: number;
    momentumMeanAnnualized: number;
    broadIndexAnnualized: number;
    strategyMinusEqualPp: number;
    strategyMinusMomentumPp: number;
    beatsEqual: boolean;
    beatsMomentum: boolean;
    preStatedHeld: boolean;
  };
}
export function getRotation(): RotationJson {
  return readJson<RotationJson>("backtest-rotation");
}

// ────────────────────────────────────────────────────────────────────
// listings-live.json + postings-live.json — Bright Data layer
// ────────────────────────────────────────────────────────────────────
export interface ListingsMetro {
  n: number;
  medianAskingRent: number | null;
  concessionShare: number | null;
  concessionsCount: number;
}
export interface ListingsLiveJson {
  fetched_at: string;
  metros: Record<string, ListingsMetro | { error: string }>;
}
export function getListingsLive(): ListingsLiveJson {
  return readJson<ListingsLiveJson>("listings-live");
}

export interface PostingsLiveMetro {
  n?: number;
  raw?: number;
  kept?: number;
  droppedRemote?: number;
  droppedOld?: number;
  deduped?: number;
}
export interface PostingsLiveJson {
  fetched_at: string;
  metros: Record<string, PostingsLiveMetro | { error: string }>;
}
export function getPostingsLive(): PostingsLiveJson {
  return readJson<PostingsLiveJson>("postings-live");
}

// ────────────────────────────────────────────────────────────────────
// Dataset meta — for the Data Sources file inventory
// ────────────────────────────────────────────────────────────────────
export interface DatasetMeta {
  key: string;
  label: string;
  file: string;
  mechanism: string;
  isBD: boolean;
  size: number;
  mtime: string | null;
  rows?: number;
  lastDate?: string;
}

export function getDatasetMeta(): DatasetMeta[] {
  const items: Omit<DatasetMeta, "size" | "mtime">[] = [
    { key: "detection", label: "Detection turns", file: "detection.json", mechanism: "Walk-forward confirmed turn detector, all 17 metros", isBD: false },
    { key: "results", label: "Lead-lag results", file: "results.json", mechanism: "YoY × YoY Pearson sweep ±12mo, every (metro, signal, target)", isBD: false },
    { key: "forecast-skill", label: "Forecast skill", file: "forecast-skill.json", mechanism: "Engine vs persistence + base-rate baselines (Brier + BSS)", isBD: false },
    { key: "backtest", label: "Naive trading test", file: "backtest.json", mechanism: "4 metros, quarterly rebalance, walk-forward (rent appreciation)", isBD: false },
    { key: "backtest-rotation", label: "Price-rotation test", file: "backtest-rotation.json", mechanism: "17 metros, 2-4yr CRE holds, ZHVI (price appreciation)", isBD: false },
    { key: "listings-live", label: "Apartments.com live", file: "listings-live.json", mechanism: "Bright Data Web Unlocker → Sonnet 4.6 extraction, 17 metros", isBD: true },
    { key: "postings-live", label: "LinkedIn live", file: "postings-live.json", mechanism: "Bright Data Web Unlocker → Sonnet 4.6 extraction, 17 metros, ≤21d", isBD: true },
    { key: "metro-id-map", label: "Metro ID map", file: "metro-id-map.json", mechanism: "Canonical metro slugs + display names + tiers", isBD: false },
  ];
  return items.map((it) => {
    const s = statSafe(it.key);
    return {
      ...it,
      size: s?.size ?? 0,
      mtime: s?.mtime ?? null,
    };
  });
}

export function ageString(iso: string | null): string {
  if (!iso) return "—";
  const ageHours = (Date.now() - new Date(iso).getTime()) / 36e5;
  if (ageHours < 1) return `${Math.round(ageHours * 60)}m ago`;
  if (ageHours < 36) return `${Math.round(ageHours)}h ago`;
  return `${Math.round(ageHours / 24)}d ago`;
}

export function fmtKB(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${Math.round(bytes / 1024)} KB`;
}
