"use client";
// Content moved from app/page.tsx so app/page.tsx can become a server
// component that reads data/laurie-engine/ JSON via fs and passes the
// overview down as props. The chat workspace (when messages.length > 0)
// is literally unchanged from Salim's original page.tsx — only the
// landing branch (messages.length === 0) now renders <LandingOverview>
// instead of the original Google-style prompt.
import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import Link from "next/link";
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
  // Tracks the in-flight stream so reset/new-turn can cancel it. See
  // resetChat() / send() — without this, late SSE events (e.g. a token
  // arriving milliseconds after the user clicks the logo) try to mutate
  // a messages array that's already been reset to [] and crash.
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  // Abort any in-flight stream on unmount as a final safety net.
  useEffect(() => () => abortRef.current?.abort(), []);

  async function send(text: string) {
    const q = text.trim();
    if (!q || busy) return;
    // If a prior stream is somehow still in flight (e.g. user starts
    // a follow-up before the previous one completed), tear it down
    // before launching the new one.
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const { signal } = controller;

    setInput("");
    turnRef.current += 1;
    const turn = turnRef.current;
    setMessages((p) => [...p, { role: "user", text: q }, { role: "assistant", text: "" }]);
    setBusy(true);
    setToolStatus("thinking…");
    try {
      await streamChat(q, sessionRef.current, (e) => {
        // Defense in depth: even if the abort fires mid-handler, a
        // buffered event from the same parse batch may still call us.
        // Bail before touching any state.
        if (signal.aborted) return;

        if (e.type === "session") sessionRef.current = e.session_id;
        else if (e.type === "token")
          setMessages((p) => {
            // Race guard: a late token after a reset would see an empty
            // array. Don't try to append to nothing.
            if (p.length === 0) return p;
            const c = [...p];
            const last = c[c.length - 1];
            c[c.length - 1] = { ...last, text: last.text + e.text };
            return c;
          });
        else if (e.type === "tool_call") setToolStatus(`querying ${e.name}…`);
        else if (e.type === "artifact") {
          // Don't append stale artifacts to a fresh landing — if the
          // user has navigated away (messages reset), drop them.
          setArtifacts((p) => (signal.aborted ? p : [...p, { ...e.artifact, turn }]));
        }
        else if (e.type === "error")
          setMessages((p) => {
            if (p.length === 0) return p;
            const c = [...p];
            const last = c[c.length - 1];
            c[c.length - 1] = { ...last, text: (last.text || "") + `\n\n_error: ${e.message}_` };
            return c;
          });
      }, signal);
    } catch (err: unknown) {
      // Intentional cancellation — silent. Not a real error.
      if (signal.aborted) return;
      if (err instanceof DOMException && err.name === "AbortError") return;
      const msg = err instanceof Error ? err.message : String(err);
      setMessages((p) => {
        if (p.length === 0) return p;
        const c = [...p];
        const last = c[c.length - 1];
        c[c.length - 1] = { ...last, text: `_connection error: ${msg}_` };
        return c;
      });
    } finally {
      // Only clear busy/status if this is still the active stream.
      // (A newer send() may have already replaced abortRef.current.)
      if (abortRef.current === controller) {
        setBusy(false);
        setToolStatus(null);
        abortRef.current = null;
      }
    }
  }

  // Reset to landing. Tears down the active stream so late SSE events
  // can't crash the freshly-empty messages array. Used by:
  //   - clickable HomeStar logo in chat header
  //   - "← Markets overview" affordance
  //   - (future) any other path that flips messages.length back to 0
  const resetChat = () => {
    abortRef.current?.abort();
    abortRef.current = null;
    setMessages([]);
    setArtifacts([]);
    setBusy(false);
    setToolStatus(null);
    sessionRef.current = null;
  };

  // ---------- landing ----------
  if (messages.length === 0) {
    return <LandingOverview overview={overview} fetchedAt={fetchedAt} onAsk={send} />;
  }

  // ---------- chat workspace ----------
  return (
    <main className="flex h-screen flex-col">
      <header className="flex items-center justify-between border-b border-black/[0.06] px-5 py-3">
        <button
          onClick={resetChat}
          title="Back to markets overview"
          className="flex items-center gap-2 hover:opacity-75 transition cursor-pointer"
        >
          <Image src="/logo.png" alt="HomeStar" width={28} height={28} priority />
          <span className="text-sm font-semibold text-ground-ink">
            Home<span className="text-ground">Star</span>
          </span>
        </button>
        <div className="flex items-center gap-5">
          <Link
            href="/pitch"
            className="text-[11px] uppercase tracking-[0.16em] text-black/40 hover:text-ground transition"
          >
            Pitch ↗
          </Link>
          <button
            onClick={resetChat}
            className="text-xs text-black/40 hover:text-ground transition"
          >
            ← Markets overview
          </button>
        </div>
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
