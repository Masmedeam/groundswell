"use client";
import { useEffect, useRef, useState } from "react";
import ChatPanel from "@/components/ChatPanel";
import CanvasPanel from "@/components/CanvasPanel";
import { streamChat } from "@/lib/api";
import type { Artifact, ChatMessage } from "@/lib/types";

const EXAMPLES = [
  "Give me the full market board for San Francisco.",
  "Compare all five metros across rent, labor, supply, and layoffs.",
  "Show the WARN layoff timeline for Austin.",
  "Show live apartment comps in Phoenix.",
  "Map ZIP-level rent in Chicago.",
];

export default function Home() {
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
    } catch (err: any) {
      setMessages((p) => {
        const c = [...p];
        c[c.length - 1] = { ...c[c.length - 1], text: `_connection error: ${err?.message || err}_` };
        return c;
      });
    } finally {
      setBusy(false);
      setToolStatus(null);
    }
  }

  // ---------- landing ----------
  if (messages.length === 0) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center px-4">
        <div className="w-full max-w-2xl text-center">
          <h1 className="text-4xl font-semibold tracking-tight text-ground-ink">
            Home<span className="text-ground">Star</span>
          </h1>
          <p className="mt-2 text-sm text-black/50">
            Demand-side rental market intelligence — ask about any U.S. metro.
          </p>
          <form
            onSubmit={(e) => { e.preventDefault(); send(input); }}
            className="mt-8 flex items-center gap-2 rounded-2xl border border-black/10 bg-white p-2 shadow-sm focus-within:border-ground"
          >
            <input
              autoFocus
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="e.g. Is rent growth firming or cooling in San Francisco?"
              className="flex-1 bg-transparent px-3 py-2 text-[15px] outline-none placeholder:text-black/30"
            />
            <button type="submit" className="rounded-xl bg-ground px-4 py-2 text-sm font-medium text-white hover:opacity-90">
              Ask
            </button>
          </form>
          <div className="mt-5 flex flex-wrap justify-center gap-2">
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                onClick={() => send(ex)}
                className="rounded-full border border-black/10 bg-white px-3 py-1.5 text-xs text-black/60 hover:border-ground hover:text-ground"
              >
                {ex}
              </button>
            ))}
          </div>
        </div>
      </main>
    );
  }

  // ---------- workspace ----------
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
      <div className="flex min-h-0 flex-1 flex-col md:flex-row">
        {/* left: chat */}
        <section className="flex min-h-[42vh] w-full flex-col border-b border-black/[0.06] md:min-h-0 md:w-[44%] md:min-w-[360px] md:border-b-0 md:border-r">
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
        <section className="flex-1 overflow-auto scroll-thin bg-[#FAFAFA] px-4 py-4 md:px-5 md:py-5">
          <CanvasPanel artifacts={artifacts} />
        </section>
      </div>
    </main>
  );
}
