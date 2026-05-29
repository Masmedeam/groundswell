"use client";
import ArtifactCard from "./Artifacts";
import type { Artifact } from "@/lib/types";

export default function CanvasPanel({ artifacts }: { artifacts: Artifact[] }) {
  if (!artifacts.length) {
    return (
      <div className="flex h-full items-center justify-center text-center text-sm text-black/35">
        <div>
          <div className="mb-1 text-base text-black/50">Analytics canvas</div>
          Charts, maps, and the data behind every answer appear here.
        </div>
      </div>
    );
  }
  // group by turn, newest turn first
  const turns = Array.from(new Set(artifacts.map((a) => a.turn ?? 0))).sort((a, b) => b - a);
  return (
    <div className="space-y-6">
      {turns.map((t) => (
        <div key={t} className="space-y-3">
          {artifacts.filter((a) => (a.turn ?? 0) === t).map((a) => (
            <ArtifactCard key={a.id} artifact={a} />
          ))}
        </div>
      ))}
    </div>
  );
}
