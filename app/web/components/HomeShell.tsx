"use client";
// Content moved from app/page.tsx so app/page.tsx can become a server
// component that reads data/laurie-engine/ JSON via fs and passes the
// overview down as props. The chat workspace (when messages.length > 0)
// is literally unchanged from Salim's original page.tsx — only the
// landing branch (messages.length === 0) now renders <LandingOverview>
// instead of the original Google-style prompt.
import { useEffect, useRef, useState } from "react";
import ChatPanel from "@/components/ChatPanel";
import CanvasPanel from "@/components/CanvasPanel";
import LandingOverview from "@/components/LandingOverview";
import { streamChat } from "@/lib/api";
import type { Artifact, ChatMessage } from "@/lib/types";
import type { MetroOverview } from "@/lib/engine-overview";

export default function HomeShell({
  overview,
  fetchedAt,
}: {
  overview: MetroOverview[];
  fetchedAt: string;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [toolStatus, setToolStatus] = useState<string | null>(null);
  const sessionRef = useRef<string | null>(null);
  const turnRef = useRef(0);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  async function send(text: string) {
    const q = text.trim();
    if (!q || busy) return;
    setInput("");
    turnRef.current += 1;
    const turn = turnRef.current;
    setMessages((p) => [...p, { role: "user", text: q }, { role: "assistant", text: "" }]);
    setBusy(true);
    setToolStatus("thinking…");
    try {
      await streamChat(q, sessionRef.current, (e) => {
        if (e.type === "session") sessionRef.current = e.session_id;
        else if (e.type === "token")
          setMessages((p) => {
            const c = [...p];
            c[c.length - 1] = { ...c[c.length - 1], text: c[c.length - 1].text + e.text };
            return c;
          });
        else if (e.type === "tool_call") setToolStatus(`querying ${e.name}…`);
        else if (e.type === "artifact") setArtifacts((p) => [...p, { ...e.artifact, turn }]);
        else if (e.type === "error")
          setMessages((p) => {
            const c = [...p];
            c[c.length - 1] = { ...c[c.length - 1], text: (c[c.length - 1].text || "") + `\n\n_error: ${e.message}_` };
            return c;
          });
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setMessages((p) => {
        const c = [...p];
        c[c.length - 1] = { ...c[c.length - 1], text: `_connection error: ${msg}_` };
        return c;
      });
    } finally {
      setBusy(false);
      setToolStatus(null);
    }
  }

  // ---------- landing (NEW — replaces the original Google-style prompt) ----------
  if (messages.length === 0) {
    return <LandingOverview overview={overview} fetchedAt={fetchedAt} onAsk={send} />;
  }

  // ---------- chat workspace (UNCHANGED from Salim's original page.tsx) ----------
  return (
    <main className="flex h-screen flex-col">
      <header className="flex items-center justify-between border-b border-black/[0.06] px-5 py-3">
        <div className="text-sm font-semibold">Home<span className="text-ground">Star</span></div>
        <button
          onClick={() => { setMessages([]); setArtifacts([]); sessionRef.current = null; }}
          className="text-xs text-black/40 hover:text-ground"
        >
          New question
        </button>
      </header>
      <div className="flex min-h-0 flex-1">
        {/* left: chat */}
        <section className="flex w-[44%] min-w-[360px] flex-col border-r border-black/[0.06]">
          <div className="flex-1 overflow-auto scroll-thin px-5 py-5">
            <ChatPanel messages={messages} busy={busy} toolStatus={toolStatus} />
            <div ref={bottomRef} />
          </div>
          <form
            onSubmit={(e) => { e.preventDefault(); send(input); }}
            className="border-t border-black/[0.06] p-3"
          >
            <div className="flex items-center gap-2 rounded-xl border border-black/10 bg-white p-1.5 focus-within:border-ground">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask a follow-up…"
                className="flex-1 bg-transparent px-3 py-1.5 text-sm outline-none placeholder:text-black/30"
              />
              <button
                type="submit"
                disabled={busy}
                className="rounded-lg bg-ground px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-40"
              >
                Send
              </button>
            </div>
          </form>
        </section>
        {/* right: canvas */}
        <section className="flex-1 overflow-auto scroll-thin bg-[#FAFAFA] px-5 py-5">
          <CanvasPanel artifacts={artifacts} />
        </section>
      </div>
    </main>
  );
}
