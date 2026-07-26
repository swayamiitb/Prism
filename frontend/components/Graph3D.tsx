"use client";

import { useEffect, useRef, useMemo } from "react";
import dynamic from "next/dynamic";
import { colorForLabel, type GraphData, type GraphNode } from "@/lib/api";

// react-force-graph-3d is browser-only; load it dynamically with ssr:false.
const ForceGraph3D = dynamic(() => import("react-force-graph-3d"), { ssr: false });

interface Props {
  data: GraphData;
  selectedId: string | number | null;
  highlightSet: Set<string | number> | null;
  onSelectNode: (node: GraphNode | null) => void;
  onHoverNeighbors: (ids: Set<string | number> | null) => void;
}

export default function Graph3D({ data, selectedId, highlightSet, onSelectNode, onHoverNeighbors }: Props) {
  const fgRef = useRef<any>(null);

  // Index edges by node id for neighbor lookup on hover.
  const neighborMap = useMemo(() => {
    const m = new Map<string | number, Set<string | number>>();
    for (const e of data.edges) {
      if (!m.has(e.source)) m.set(e.source, new Set());
      if (!m.has(e.target)) m.set(e.target, new Set());
      m.get(e.source)!.add(e.target);
      m.get(e.target)!.add(e.source);
    }
    return m;
  }, [data.edges]);

  // Build the node/edge payload the library expects.
  const graph = useMemo(() => {
    const links = data.edges.map((e) => ({ source: e.source, target: e.target, type: e.type }));
    const nodes = data.nodes.map((n) => ({ ...n }));
    return { nodes, links };
  }, [data]);

  // Gentle auto-rotation when idle — gives the "living constellation" feel.
  useEffect(() => {
    const fg = fgRef.current;
    if (!fg) return;
    let angle = 0;
    let raf = 0;
    const distance = 320;
    const tick = () => {
      angle += 0.0008;
      const center = fg?.center || { x: 0, y: 0, z: 0 };
      fg.cameraPosition({
        x: (center.x || 0) + distance * Math.sin(angle),
        z: (center.z || 0) + distance * Math.cos(angle),
        y: center.y || 0,
      });
      raf = requestAnimationFrame(tick);
    };
    // Only rotate when nothing is selected.
    if (!selectedId) raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [selectedId]);

  const isDimmed = (id: string | number) => {
    if (!highlightSet) return false;
    return !highlightSet.has(id);
  };

  return (
    <ForceGraph3D
      ref={fgRef}
      graphData={graph}
      backgroundColor="#05060a"
      nodeLabel={(n: any) =>
        `<div style="background:#11141f;padding:6px 10px;border-radius:6px;border:1px solid #262d40">
          <b style="color:${colorForLabel(n.label)}">${n.label}</b><br/>
          <span style="color:#e2e8f0">${n.value}</span>
        </div>`
      }
      nodeColor={(n: any) => {
        if (highlightSet && isDimmed(n.id)) return "#1a1f2e";
        if (selectedId === n.id) return "#ffffff";
        return colorForLabel(n.label);
      }}
      nodeOpacity={0.95}
      nodeRelSize={5}
      nodeResolution={16}
      linkColor={(l: any) => {
        if (!highlightSet) return "rgba(120,140,180,0.35)";
        const active = highlightSet.has(l.source) && highlightSet.has(l.target);
        return active ? "rgba(34,211,238,0.9)" : "rgba(40,50,70,0.2)";
      }}
      linkWidth={0.4}
      linkDirectionalParticles={2}
      linkDirectionalParticleWidth={0.6}
      linkDirectionalParticleSpeed={0.004}
      linkDirectionalArrowLength={3.5}
      linkDirectionalArrowRelPos={1}
      linkLabel={(l: any) => l.type || ""}
      onNodeClick={(n: any) => {
        // Stop rotation by "selecting".
        onSelectNode(n as GraphNode);
        // Focus the camera on the clicked node.
        const fg = fgRef.current;
        if (fg) {
          const distance = 120;
          const distRatio = 1 + distance / 320;
          fg.cameraPosition({ x: n.x * distRatio, y: n.y * distRatio, z: n.z * distRatio }, n, 800);
        }
      }}
      onNodeHover={(n: any) => {
        if (n) {
          const neighbors = neighborMap.get(n.id) || new Set();
          onHoverNeighbors(new Set([n.id, ...neighbors]));
        } else {
          onHoverNeighbors(null);
        }
      }}
      onBackgroundClick={() => {
        onSelectNode(null);
        onHoverNeighbors(null);
      }}
      cooldownTicks={200}
      width={undefined}
      height={undefined}
    />
  );
}
