export type Source = {
  label: string; es_index?: string; query?: string; n?: number; date_range?: string;
};

export type Artifact = {
  id: string;
  type: "metric_cards" | "snapshot_board" | "timeseries" | "bar" | "heatmap" | "map" | "table" | "event_timeline" | "comps";
  title: string;
  turn?: number;
  confidence?: string;
  sources?: Source[];
  // type-specific
  cards?: any[];
  groups?: { group: string; items: any[] }[];
  lines?: { metro_id: string; points: { date: string; value: number }[] }[];
  series?: string;
  mode?: string;
  annotations?: any[];
  bars?: { metro_id: string; value: number; as_of?: string }[];
  metric?: string;
  rows?: any[];
  buckets?: { date: string; count: number; value?: number }[];
  events?: any[];
  count_label?: string;
  value_label?: string;
  items?: any[];
  regions?: { region: string; region_id?: string; value: number; as_of?: string; lat?: number | null; lng?: number | null }[];
  level?: string;
  metro_id?: string;
  columns?: string[];
  summary_text?: string;
};

export type ChatMessage = { role: "user" | "assistant"; text: string };

export type StreamEvent =
  | { type: "session"; session_id: string }
  | { type: "token"; text: string }
  | { type: "tool_call"; name: string; input: any }
  | { type: "artifact"; artifact: Artifact }
  | { type: "done" }
  | { type: "error"; message: string };
