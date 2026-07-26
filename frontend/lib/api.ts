// Typed client for the SAAS AI backend API.

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface GraphNode {
  id: number | string;
  label: string;
  value: string;
  [key: string]: unknown;
}

export interface GraphEdge {
  source: number | string;
  target: number | string;
  type: string;
  [key: string]: unknown;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface ProviderInfo {
  id: string;
  name: string;
  ok: boolean;
  detail: string;
  writable: boolean;
}

export interface GraphStats {
  node_count: number;
  edge_count: number;
  by_label: Record<string, number>;
  by_edge: Record<string, number>;
}

export interface ChatEvent {
  event: "token" | "tool" | "done" | "error";
  data: string;
}

async function getJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => getJSON<{ status: string }>("/health"),
  providers: () => getJSON<{ providers: ProviderInfo[] }>("/providers"),
  graph: (limit = 2000) => getJSON<GraphData>(`/graph?limit=${limit}`),
  graphStats: () => getJSON<GraphStats>("/graph/stats"),
  subgraph: (value: string, hops = 2) =>
    getJSON<GraphData>(`/graph/subgraph?value=${encodeURIComponent(value)}&hops=${hops}`),
  ingest: (target: string, providers?: string[]) =>
    getJSON<{ target: string; filed_nodes: number; filed_edges: number; providers_run: unknown[] }>(
      "/ingest",
      { method: "POST", body: JSON.stringify({ target, providers }) }
    ),
  chat: (message: string) =>
    getJSON<{ content: string; tool_calls: string[] }>("/chat", {
      method: "POST",
      body: JSON.stringify({ message }),
    }),

  // SSE streaming chat. Returns an async generator of parsed events.
  async *chatStream(message: string): AsyncGenerator<ChatEvent> {
    const res = await fetch(`${API_URL}/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    if (!res.body) throw new Error("no response body");
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      // SSE events are separated by blank lines.
      const events = buffer.split("\n\n");
      buffer = events.pop() || "";
      for (const block of events) {
        const lines = block.split("\n");
        let event = "message";
        let data = "";
        for (const line of lines) {
          if (line.startsWith("event:")) event = line.slice(6).trim();
          else if (line.startsWith("data:")) data += line.slice(5).trim();
        }
        if (data) yield { event: event as ChatEvent["event"], data };
      }
    }
  },
};

// Per-label color mapping for the company knowledge graph + shared legend.
export const LABEL_COLORS: Record<string, string> = {
  Process: "#22d3ee",
  Step: "#67e8f9",
  Decision: "#f472b6",
  Policy: "#a78bfa",
  Role: "#34d399",
  Team: "#6ee7b7",
  Person: "#fbbf24",
  System: "#fb923c",
  Document: "#9ca3af",
  Tag: "#94a3b8",
  Entity: "#64748b",
};

export function colorForLabel(label: string): string {
  return LABEL_COLORS[label] || LABEL_COLORS.Entity;
}

// ── Processes + Skills (the executable-skills layer) ──────────────────────

export interface CompanyProcess {
  value: string;
  label?: string;
  description?: string;
  confidence?: number;
  last_seen?: string;
}

export interface ExportedSkill {
  file: string;
  name: string;
  process: string;
  trigger?: string;
  owner?: string;
  steps: number;
  error?: string;
}

export const api2 = {
  processes: () => getJSON<{ processes: CompanyProcess[] }>("/processes"),
  process: (value: string) => getJSON<Record<string, unknown>>(`/processes/${encodeURIComponent(value)}`),
  skills: () => getJSON<{ skills: ExportedSkill[] }>("/skills"),
  readSkill: (process: string) =>
    getJSON<{ process: string; yaml: string }>(`/skills/${encodeURIComponent(process)}`),
  exportSkill: (process: string) =>
    getJSON<{ process: string; file: string }>(`/skills/${encodeURIComponent(process)}/export`, {
      method: "POST",
    }),
};
