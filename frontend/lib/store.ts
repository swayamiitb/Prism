"use client";

import { create } from "zustand";
import { api, type GraphData, type GraphStats, type ProviderInfo, type GraphNode } from "./api";

interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
  tools?: string[];
  streaming?: boolean;
}

interface SaasState {
  // Graph data
  graph: GraphData;
  stats: GraphStats | null;
  loadingGraph: boolean;
  selectedNode: GraphNode | null;
  highlightSet: Set<string | number> | null;

  // Chat
  messages: ChatMessage[];
  streaming: boolean;
  lastTools: string[];

  // Providers + ingestion
  providers: ProviderInfo[];
  ingesting: boolean;
  ingestLog: { target: string; nodes: number; edges: number; at: number }[];

  // View
  viewMode: "3d" | "2d";

  // Actions
  loadGraph: () => Promise<void>;
  loadStats: () => Promise<void>;
  loadProviders: () => Promise<void>;
  selectNode: (node: GraphNode | null) => void;
  highlightNeighbors: (ids: Set<string | number> | null) => void;
  sendMessage: (text: string) => Promise<void>;
  ingest: (target: string) => Promise<void>;
  setViewMode: (mode: "3d" | "2d") => void;
}

export const useStore = create<SaasState>((set, get) => ({
  graph: { nodes: [], edges: [] },
  stats: null,
  loadingGraph: false,
  selectedNode: null,
  highlightSet: null,
  messages: [],
  streaming: false,
  lastTools: [],
  providers: [],
  ingesting: false,
  ingestLog: [],
  viewMode: "3d",

  loadGraph: async () => {
    set({ loadingGraph: true });
    try {
      const graph = await api.graph();
      set({ graph, loadingGraph: false });
    } catch (e) {
      set({ loadingGraph: false });
      console.error("loadGraph failed", e);
    }
  },

  loadStats: async () => {
    try {
      const stats = await api.graphStats();
      set({ stats });
    } catch (e) {
      console.error("loadStats failed", e);
    }
  },

  loadProviders: async () => {
    try {
      const { providers } = await api.providers();
      set({ providers });
    } catch (e) {
      console.error("loadProviders failed", e);
    }
  },

  selectNode: (node) => set({ selectedNode: node }),
  highlightNeighbors: (ids) => set({ highlightSet: ids }),

  sendMessage: async (text) => {
    const userMsg: ChatMessage = { role: "user", content: text };
    set((s) => ({ messages: [...s.messages, userMsg], streaming: true, lastTools: [] }));

    // Placeholder assistant message we mutate as tokens stream in.
    const assistantMsg: ChatMessage = { role: "assistant", content: "", streaming: true, tools: [] };
    set((s) => ({ messages: [...s.messages, assistantMsg] }));

    try {
      let tokens = "";
      const tools: string[] = [];
      for await (const ev of api.chatStream(text)) {
        if (ev.event === "token") {
          const { text: chunk } = JSON.parse(ev.data);
          tokens += chunk;
          set((s) => {
            const msgs = [...s.messages];
            msgs[msgs.length - 1] = { ...msgs[msgs.length - 1], content: tokens };
            return { messages: msgs };
          });
        } else if (ev.event === "tool") {
          const { name } = JSON.parse(ev.data);
          tools.push(name);
          set((s) => {
            const msgs = [...s.messages];
            msgs[msgs.length - 1] = { ...msgs[msgs.length - 1], tools: [...tools] };
            return { messages: msgs, lastTools: [...tools] };
          });
        } else if (ev.event === "done") {
          set((s) => {
            const msgs = [...s.messages];
            msgs[msgs.length - 1] = { ...msgs[msgs.length - 1], streaming: false };
            return { messages: msgs, streaming: false };
          });
          // The agent likely mutated the graph — refresh it.
          get().loadGraph();
          get().loadStats();
        } else if (ev.event === "error") {
          const { detail } = JSON.parse(ev.data);
          set((s) => {
            const msgs = [...s.messages];
            msgs[msgs.length - 1] = {
              role: "assistant",
              content: `⚠️ ${detail}`,
              streaming: false,
            };
            return { messages: msgs, streaming: false };
          });
        }
      }
    } catch (e) {
      set((s) => {
        const msgs = [...s.messages];
        msgs[msgs.length - 1] = {
          role: "assistant",
          content: `⚠️ ${e instanceof Error ? e.message : "stream failed"}`,
          streaming: false,
        };
        return { messages: msgs, streaming: false };
      });
    }
  },

  ingest: async (target) => {
    set({ ingesting: true });
    try {
      const result = await api.ingest(target);
      set((s) => ({
        ingestLog: [
          { target: result.target, nodes: result.filed_nodes, edges: result.filed_edges, at: Date.now() },
          ...s.ingestLog,
        ].slice(0, 10),
      }));
      // Refresh graph after ingestion.
      await get().loadGraph();
      await get().loadStats();
    } catch (e) {
      console.error("ingest failed", e);
    } finally {
      set({ ingesting: false });
    }
  },

  setViewMode: (mode) => set({ viewMode: mode }),
}));
