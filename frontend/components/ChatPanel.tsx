"use client";

import { useState, useRef, useEffect } from "react";
import { useStore } from "@/lib/store";

const QUICK_PROMPTS = [
  "How do we handle refunds over $500?",
  "Who owns the incident-response process?",
  "What systems are used for billing?",
];

export default function ChatPanel() {
  const [input, setInput] = useState("");
  const messages = useStore((s) => s.messages);
  const streaming = useStore((s) => s.streaming);
  const sendMessage = useStore((s) => s.sendMessage);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const submit = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || streaming) return;
    setInput("");
    void sendMessage(trimmed);
  };

  return (
    <div className="flex flex-col h-full bg-ink-900/60 border border-ink-600 rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-ink-700 flex items-center gap-2">
        <span className="w-2 h-2 rounded-full bg-neon-green animate-pulse" />
        <h2 className="text-sm font-semibold text-slate-200">Context Brain</h2>
        <span className="ml-auto text-[10px] text-slate-500">gemma4 · local</span>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {messages.length === 0 && (
          <div className="text-center py-8">
            <p className="text-sm text-slate-400 mb-3">Ask how the company works. The Brain reads Slack, Drive, and the wiki — then synthesizes processes and exports executable skills.</p>
            <div className="flex flex-col gap-1.5 items-center">
              {QUICK_PROMPTS.map((p) => (
                <button
                  key={p}
                  onClick={() => submit(p)}
                  className="text-xs text-neon-cyan/80 hover:text-neon-cyan hover:underline max-w-full truncate"
                >
                  → {p}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "flex justify-end" : ""}>
            <div
              className={`max-w-[90%] rounded-lg px-3 py-2 text-sm ${
                m.role === "user"
                  ? "bg-neon-cyan/15 border border-neon-cyan/30 text-slate-100"
                  : "bg-ink-800/80 border border-ink-600 text-slate-200"
              }`}
            >
              {m.tools && m.tools.length > 0 && (
                <div className="flex flex-wrap gap-1 mb-1.5">
                  {m.tools.map((t, j) => (
                    <span key={j} className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-neon-violet/20 text-neon-violet/90">
                      {t}
                    </span>
                  ))}
                </div>
              )}
              <div className="whitespace-pre-wrap break-words">
                {m.content || (m.streaming ? <span className="text-slate-500 animate-pulse">▍</span> : "")}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Input */}
      <div className="border-t border-ink-700 p-3">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit(input)}
            placeholder={streaming ? "thinking…" : "ask how the company works…"}
            disabled={streaming}
            className="flex-1 bg-ink-950 border border-ink-600 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:outline-none focus:border-neon-cyan/50"
          />
          <button
            onClick={() => submit(input)}
            disabled={streaming || !input.trim()}
            className="px-4 py-2 rounded-lg bg-neon-cyan text-ink-950 text-sm font-semibold disabled:opacity-40 hover:brightness-110 transition"
          >
            {streaming ? "…" : "Run"}
          </button>
        </div>
      </div>
    </div>
  );
}
