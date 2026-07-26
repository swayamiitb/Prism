"use client";

import { useEffect, useRef } from "react";
import cytoscape from "cytoscape";
// @ts-ignore — no types shipped with fcose.
import fcose from "cytoscape-fcose";
import { colorForLabel, type GraphData, type GraphNode } from "@/lib/api";

cytoscape.use(fcose);

interface Props {
  data: GraphData;
  selectedId: string | number | null;
  onSelectNode: (node: GraphNode | null) => void;
  onHoverNeighbors: (ids: Set<string | number> | null) => void;
}

export default function Graph2D({ data, selectedId, onSelectNode, onHoverNeighbors }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);

  // Build / update the Cytoscape instance when data changes.
  useEffect(() => {
    if (!containerRef.current) return;

    const elements: cytoscape.ElementDefinition[] = [
      ...data.nodes.map((n) => ({
        data: { id: String(n.id), label: n.value, nodeLabel: n.label, ...n },
      })),
      ...data.edges.map((e, i) => ({
        data: { id: `e${i}`, source: String(e.source), target: String(e.target), type: e.type },
      })),
    ];

    // If a graph already exists, destroy + rebuild (simplest correct refresh).
    cyRef.current?.destroy();

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "text-valign": "bottom",
            "text-halign": "center",
            "font-size": "9px",
            color: "#94a3b8",
            width: 22,
            height: 22,
            "background-color": colorForLabel("Entity"),
            "border-width": 1,
            "border-color": "#0a0c14",
          },
        },
        {
          selector: "node:selected",
          style: { "border-width": 3, "border-color": "#ffffff", width: 28, height: 28 },
        },
        {
          selector: "edge",
          style: {
            width: 1,
            "line-color": "rgba(120,140,180,0.3)",
            "target-arrow-color": "rgba(120,140,180,0.4)",
            "target-arrow-shape": "triangle",
            "arrow-scale": 0.6,
            "curve-style": "bezier",
          },
        },
        {
          selector: ".faded",
          style: { opacity: 0.15 },
        },
        {
          selector: ".highlighted",
          style: { "line-color": "#22d3ee", "target-arrow-color": "#22d3ee", width: 2 },
        },
      ],
      layout: {
        name: "fcose",
        animate: true,
        animationDuration: 800,
        nodeRepulsion: 8000,
        idealEdgeLength: 80,
        packComponents: true,
      } as any,
    });

    // Apply per-label colors via a function-based style override (cleaner than
    // a duplicate selector and keeps the shared palette in sync).
    cy.style()
      .selector("node")
      .style({ "background-color": (ele: any) => colorForLabel(ele.data("nodeLabel")) as any })
      .update();

    cy.on("tap", "node", (evt) => {
      onSelectNode(evt.target.data() as unknown as GraphNode);
    });
    cy.on("tap", (evt) => {
      if (evt.target === cy) onSelectNode(null);
    });
    cy.on("mouseover", "node", (evt) => {
      const id = evt.target.id();
      const neighborhood = new Set<string | number>([id]);
      evt.target.neighborhood().forEach((n) => neighborhood.add(n.id()));
      onHoverNeighbors(neighborhood);
      cy.elements()
        .removeClass("faded highlighted")
        .difference(evt.target.closedNeighborhood())
        .addClass("faded");
      evt.target.neighborhood("edge").addClass("highlighted");
    });
    cy.on("mouseout", "node", () => {
      onHoverNeighbors(null);
      cy.elements().removeClass("faded highlighted");
    });

    cyRef.current = cy;
    return () => {
      cy.destroy();
      cyRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  // Reflect external selection in the 2D view.
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.$(":selected").unselect();
    if (selectedId != null) {
      const el = cy.getElementById(String(selectedId));
      if (el && el.length) el.select();
    }
  }, [selectedId]);

  return <div ref={containerRef} className="w-full h-full" />;
}
