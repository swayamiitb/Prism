"use client";

import { useStore } from "@/lib/store";
import { colorForLabel } from "@/lib/api";

export default function EntityInspector() {
  const node = useStore((s) => s.selectedNode);

  if (!node) {
    return (
      <div className="bg-ink-900/60 border border-ink-600 rounded-xl p-4 text-center">
        <p className="text-xs text-slate-500">Select a node to inspect its properties.</p>
      </div>
    );
  }

  const entries = Object.entries(node).filter(([k]) => k !== "id");
  const color = colorForLabel(node.label);

  return (
    <div className="bg-ink-900/60 border border-ink-600 rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-ink-700 flex items-center gap-2">
        <span className="w-3 h-3 rounded-full text-glow" style={{ background: color }} />
        <h3 className="text-sm font-semibold text-slate-100 truncate">{node.value}</h3>
      </div>
      <div className="px-4 py-3">
        <div className="inline-block text-[10px] font-mono px-2 py-0.5 rounded-full mb-3" style={{ background: `${color}22`, color }}>
          {node.label}
        </div>
        <dl className="space-y-2">
          {entries.map(([key, value]) => (
            <div key={key} className="grid grid-cols-3 gap-2 text-xs">
              <dt className="text-slate-500 font-mono">{key}</dt>
              <dd className="col-span-2 text-slate-200 break-words">
                {typeof value === "object" ? JSON.stringify(value) : String(value)}
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  );
}
