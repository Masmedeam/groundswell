export type Source = {
  label: string; es_index?: string; query?: string; n?: number; date_range?: string;
};

export type Artifact = {
  id: string;
  type: "metric_cards" | "timeseries" | "bar" | "map" | "table";
  title: string;
  turn?: number;
  confidence?: string;
  sources?: Source[];
  // type-specific
  cards?: any[];
  lines?: { metro_id: string; points: { date: string; value: number }[] }[];
  series?: string;
  annotations?: any[];
  bars?: { metro_id: string; value: number; as_of?: string }[];
  metric?: string;
  regions?: { region: string; region_id?: string; value: number; as_of?: string; lat?: number | null; lng?: number | null }[];
  level?: string;
  metro_id?: string;
  columns?: string[];
  rows?: any[];
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
