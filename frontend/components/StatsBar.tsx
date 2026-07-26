"use client";

import { useEffect } from "react";
import { useStore } from "@/lib/store";

export default function StatsBar() {
  const stats = useStore((s) => s.stats);
  const providers = useStore((s) => s.providers);
  const loadStats = useStore((s) => s.loadStats);
  const loadProviders = useStore((s) => s.loadProviders);

  useEffect(() => {
    loadStats();
    loadProviders();
    const id = setInterval(() => {
      loadStats();
      loadProviders();
    }, 10000);
    return () => clearInterval(id);
  }, [loadStats, loadProviders]);

  const okProviders = providers.filter((p) => p.ok).length;

  return (
    <div className="flex items-center gap-4 px-4 py-2.5 bg-ink-900/80 backdrop-blur border border-ink-600 rounded-xl">
      <div className="flex items-center gap-1.5">
        <span className="text-lg font-bold text-neon-cyan text-glow">{stats?.node_count ?? 0}</span>
        <span className="text-[10px] text-slate-500 uppercase tracking-wider">nodes</span>
      </div>
      <div className="w-px h-5 bg-ink-600" />
      <div className="flex items-center gap-1.5">
        <span className="text-lg font-bold text-neon-violet text-glow">{stats?.edge_count ?? 0}</span>
        <span className="text-[10px] text-slate-500 uppercase tracking-wider">edges</span>
      </div>
      <div className="w-px h-5 bg-ink-600" />
      <div className="flex items-center gap-1.5">
        <span className="w-2 h-2 rounded-full bg-neon-green animate-pulse" />
        <span className="text-xs text-slate-300">
          {okProviders}/{providers.length} sources
        </span>
      </div>
      <div className="ml-auto flex items-center gap-3">
        {stats?.by_label &&
          Object.entries(stats.by_label)
            .slice(0, 6)
            .map(([label, count]) => (
              <span key={label} className="text-[10px] text-slate-500">
                {label}: <span className="text-slate-300">{count}</span>
              </span>
            ))}
      </div>
    </div>
  );
}
