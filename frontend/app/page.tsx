"use client";

import GraphView from "@/components/GraphView";
import ChatPanel from "@/components/ChatPanel";
import EntityInspector from "@/components/EntityInspector";
import StatsBar from "@/components/StatsBar";
import SkillsExplorer from "@/components/SkillsExplorer";

export default function Home() {
  return (
    <main className="h-screen flex flex-col p-3 gap-3 overflow-hidden">
      {/* Header */}
      <header className="flex items-center gap-3 px-1 shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-2xl">🧠</span>
          <div>
            <h1 className="text-lg font-bold tracking-tight">
              <span className="text-neon-cyan text-glow">Company</span>{" "}
              <span className="text-slate-100">Brain</span>
            </h1>
            <p className="text-[10px] text-slate-500 -mt-0.5">How the company works · executable skills · local models</p>
          </div>
        </div>
        <div className="ml-auto">
          <StatsBar />
        </div>
      </header>

      {/* Main split: graph canvas | right rail */}
      <div className="flex-1 flex gap-3 min-h-0">
        {/* Graph canvas */}
        <div className="flex-1 bg-ink-950/40 border border-ink-600 rounded-xl overflow-hidden relative">
          <GraphView />
        </div>

        {/* Right rail: chat + inspector + skills */}
        <aside className="w-[380px] shrink-0 flex flex-col gap-3 min-h-0 overflow-y-auto">
          <div className="flex-1 min-h-[300px]">
            <ChatPanel />
          </div>
          <EntityInspector />
          <SkillsExplorer />
        </aside>
      </div>
    </main>
  );
}
