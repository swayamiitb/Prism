"use client";

import { useEffect } from "react";
import Graph3D from "./Graph3D";
import Graph2D from "./Graph2D";
import { useStore } from "@/lib/store";
import { LABEL_COLORS } from "@/lib/api";

export default function GraphView() {
  const graph = useStore((s) => s.graph);
  const loadingGraph = useStore((s) => s.loadingGraph);
  const viewMode = useStore((s) => s.viewMode);
  const setViewMode = useStore((s) => s.setViewMode);
  const selectedNode = useStore((s) => s.selectedNode);
  const selectNode = useStore((s) => s.selectNode);
  const highlightSet = useStore((s) => s.highlightSet);
  const highlightNeighbors = useStore((s) => s.highlightNeighbors);
  const loadGraph = useStore((s) => s.loadGraph);

  useEffect(() => {
    loadGraph();
    const id = setInterval(loadGraph, 8000); // live-refresh the constellation
    return () => clearInterval(id);
  }, [loadGraph]);

  const empty = graph.nodes.length === 0;

  return (
    <div className="relative w-full h-full">
      {/* View toggle */}
      <div className="absolute top-4 left-4 z-10 flex gap-1 bg-ink-900/80 backdrop-blur border border-ink-600 rounded-lg p-1">
        <button
          onClick={() => setViewMode("3d")}
          className={`px-3 py-1.5 text-xs font-medium rounded-md transition ${
            viewMode === "3d" ? "bg-neon-cyan text-ink-950" : "text-slate-400 hover:text-slate-200"
          }`}
        >
          ◳ 3D
        </button>
        <button
          onClick={() => setViewMode("2d")}
          className={`px-3 py-1.5 text-xs font-medium rounded-md transition ${
            viewMode === "2d" ? "bg-neon-cyan text-ink-950" : "text-slate-400 hover:text-slate-200"
          }`}
        >
          ◱ 2D
        </button>
        <button
          onClick={loadGraph}
          className="px-3 py-1.5 text-xs font-medium rounded-md text-slate-400 hover:text-slate-200"
          title="Refresh graph"
        >
          ↻
        </button>
      </div>

      {/* Legend */}
      <div className="absolute top-4 right-4 z-10 bg-ink-900/80 backdrop-blur border border-ink-600 rounded-lg p-3 max-w-[180px]">
        <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-2">Legend</div>
        <div className="grid grid-cols-2 gap-x-3 gap-y-1">
          {Object.entries(LABEL_COLORS).map(([label, color]) => (
            <div key={label} className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full" style={{ background: color }} />
              <span className="text-[10px] text-slate-400">{label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Empty state */}
      {empty && !loadingGraph && (
        <div className="absolute inset-0 flex items-center justify-center z-10 pointer-events-none">
          <div className="text-center max-w-md px-6">
            <div className="text-5xl mb-4">🧠</div>
            <h3 className="text-lg font-semibold text-slate-200 mb-1">The Brain is empty</h3>
            <p className="text-sm text-slate-500">
              Ask how the company handles something (e.g. "how do we handle refunds over $500?").
              The Brain synthesizes a process and it appears here as a connected graph.
            </p>
          </div>
        </div>
      )}

      {loadingGraph && empty && (
        <div className="absolute inset-0 flex items-center justify-center z-10">
          <div className="text-neon-cyan animate-pulse text-sm">Loading graph…</div>
        </div>
      )}

      {/* The canvas fills its container; Graph3D/2D are absolute. */}
      <div className="absolute inset-0">
        {viewMode === "3d" ? (
          <Graph3D
            data={graph}
            selectedId={selectedNode?.id ?? null}
            highlightSet={highlightSet}
            onSelectNode={selectNode}
            onHoverNeighbors={highlightNeighbors}
          />
        ) : (
          <Graph2D
            data={graph}
            selectedId={selectedNode?.id ?? null}
            onSelectNode={selectNode}
            onHoverNeighbors={highlightNeighbors}
          />
        )}
      </div>
    </div>
  );
}
