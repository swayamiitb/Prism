"use client";

import { useEffect, useState } from "react";
import { api2, type ExportedSkill } from "@/lib/api";

export default function SkillsExplorer() {
  const [skills, setSkills] = useState<ExportedSkill[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  const [yaml, setYaml] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api2.skills().then((d) => setSkills(d.skills)).catch(() => setSkills([]));
  }, []);

  const viewSkill = async (process: string) => {
    if (open === process) {
      setOpen(null);
      return;
    }
    setLoading(true);
    try {
      const res = await api2.readSkill(process);
      setYaml(res.yaml);
      setOpen(process);
    } catch {
      setYaml("// skill file not found");
      setOpen(process);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-ink-900/60 border border-ink-600 rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-ink-700 flex items-center gap-2">
        <span className="text-sm">⚙️</span>
        <h3 className="text-sm font-semibold text-slate-200">Executable Skills</h3>
        <span className="ml-auto text-[10px] text-slate-500">.skill.yml · agent-loadable</span>
      </div>
      <div className="p-3">
        {skills.length === 0 ? (
          <p className="text-xs text-slate-500 text-center py-3">
            No skills exported yet. Ask the Brain how the company handles something — it synthesizes a process and exports a skill file.
          </p>
        ) : (
          <div className="space-y-2">
            {skills.map((s) => (
              <div key={s.file}>
                <button
                  onClick={() => viewSkill(s.process || s.name)}
                  className="w-full text-left px-3 py-2 rounded-lg bg-ink-950 border border-ink-600 hover:border-neon-cyan/40 transition"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium text-neon-cyan">{s.name}</span>
                    <span className="ml-auto text-[10px] text-slate-500">{s.steps} steps</span>
                  </div>
                  {s.trigger && <div className="text-[10px] text-slate-500 mt-0.5 truncate">→ {s.trigger}</div>}
                </button>
                {open === (s.process || s.name) && (
                  <pre className="mt-1 p-3 bg-ink-950 border border-ink-700 rounded-lg text-[10px] text-slate-300 overflow-x-auto max-h-60 font-mono whitespace-pre-wrap">
                    {loading ? "loading…" : yaml}
                  </pre>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
