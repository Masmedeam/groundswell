import type { StreamEvent } from "./types";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/** POST /chat and parse the SSE stream, invoking onEvent for each event. */
export async function streamChat(
  message: string,
  sessionId: string | null,
  onEvent: (e: StreamEvent) => void
): Promise<void> {
  const res = await fetch(`${API}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId }),
  });
  if (!res.body) throw new Error("no response body");
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop() || "";
    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data:")) continue;
      try {
        onEvent(JSON.parse(line.slice(5).trim()) as StreamEvent);
      } catch {
        /* ignore partial */
      }
    }
  }
}
