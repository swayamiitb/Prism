"use client";

import { useState } from "react";
import { useStore } from "@/lib/store";

export default function IngestConsole() {
  const [target, setTarget] = useState("");
  const ingest = useStore((s) => s.ingest);
  const ingesting = useStore((s) => s.ingesting);
  const ingestLog = useStore((s) => s.ingestLog);

  const submit = () => {
    const t = target.trim();
    if (!t || ingesting) return;
    setTarget("");
    void ingest(t);
  };

  return (
    <div className="bg-ink-900/60 border border-ink-600 rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-ink-700">
        <h3 className="text-sm font-semibold text-slate-200">Synthesize</h3>
        <p className="text-[10px] text-slate-500 mt-0.5">Ask the Brain to synthesize a process into the graph + export its skill file.</p>
      </div>
      <div className="p-3">
        <div className="flex gap-2">
          <input
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
            placeholder="how do we handle refunds over $500?"
            disabled={ingesting}
            className="flex-1 bg-ink-950 border border-ink-600 rounded-lg px-3 py-2 text-xs text-slate-100 placeholder:text-slate-600 focus:outline-none focus:border-neon-green/50"
          />
          <button
            onClick={submit}
            disabled={ingesting || !target.trim()}
            className="px-3 py-2 rounded-lg bg-neon-green/90 text-ink-950 text-xs font-semibold disabled:opacity-40 hover:brightness-110 transition"
          >
            {ingesting ? "Synthesizing…" : "Synthesize"}
          </button>
        </div>
        {ingestLog.length > 0 && (
          <div className="mt-3 space-y-1 max-h-32 overflow-y-auto">
            {ingestLog.map((entry, i) => (
              <div key={i} className="text-[10px] text-slate-500 flex items-center gap-2">
                <span className="text-neon-green">+{entry.nodes}n</span>
                <span className="text-neon-violet">+{entry.edges}e</span>
                <span className="text-slate-400 truncate">{entry.target}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
