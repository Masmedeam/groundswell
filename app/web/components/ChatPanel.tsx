"use client";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatMessage } from "@/lib/types";

export default function ChatPanel({
  messages, busy, toolStatus,
}: { messages: ChatMessage[]; busy: boolean; toolStatus: string | null }) {
  return (
    <div className="space-y-5">
      {messages.map((m, i) => (
        <div key={i}>
          {m.role === "user" ? (
            <div className="ml-auto w-fit max-w-[90%] rounded-2xl bg-ground text-white px-4 py-2 text-sm">
              {m.text}
            </div>
          ) : (
            <div className="prose-gw max-w-none text-[15px] text-ground-ink">
              {m.text ? (
                <Markdown remarkPlugins={[remarkGfm]}>{m.text}</Markdown>
              ) : (
                <span className="text-black/40">…</span>
              )}
            </div>
          )}
        </div>
      ))}
      {busy && toolStatus && (
        <div className="flex items-center gap-2 text-xs text-ground">
          <span className="h-2 w-2 animate-pulse rounded-full bg-ground" />
          {toolStatus}
        </div>
      )}
    </div>
  );
}
