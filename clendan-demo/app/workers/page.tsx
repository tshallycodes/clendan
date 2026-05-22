"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { WorkerCard } from "@/components/ui/WorkerCard";
import { WORKERS } from "@/lib/constants";
import { cn } from "@/lib/utils";

type Filter = "All" | "MVP" | "V2" | "V3";

export default function WorkersPage() {
  const [filter, setFilter] = useState<Filter>("All");
  const [selected, setSelected] = useState<(typeof WORKERS)[0] | null>(null);

  const filtered = filter === "All" ? WORKERS : WORKERS.filter((w) => w.badge === filter);

  return (
    <>
      <Navbar />
      <main className="pt-20 min-h-screen">
        {/* Hero */}
        <div className="max-w-4xl mx-auto px-6 py-20 text-center border-b border-brand-border">
          <p className="text-[10px] font-mono text-brand-muted uppercase tracking-widest mb-3">AI Workers</p>
          <h1 className="font-heading text-4xl md:text-5xl font-extrabold text-brand-text mb-4">
            10 AI Workers. Every Finance Function.
          </h1>
          <p className="text-brand-muted font-mono text-sm max-w-xl mx-auto">
            Pre-built agents for accounts payable, reconciliation, collections, fraud detection, and more.
            Deploy MVP workers today, unlock V2 and V3 as you scale.
          </p>
        </div>

        <div className="max-w-7xl mx-auto px-6 py-16">
          {/* Filter tabs */}
          <div className="flex gap-2 mb-8">
            {(["All", "MVP", "V2", "V3"] as Filter[]).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={cn(
                  "text-xs font-mono px-4 py-2 rounded-sm border transition-colors",
                  filter === f
                    ? "bg-brand-surface border-brand-border text-brand-text"
                    : "border-transparent text-brand-muted hover:text-brand-text"
                )}
              >
                {f} {f !== "All" && `(${WORKERS.filter((w) => w.badge === f).length})`}
              </button>
            ))}
          </div>

          {/* Worker grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {filtered.map((worker) => (
              <WorkerCard
                key={worker.id}
                name={worker.name}
                description={worker.description}
                badge={worker.badge}
                tools={worker.tools}
                status={worker.status}
                onClick={() => setSelected(worker)}
              />
            ))}
          </div>
        </div>

        {/* Detail panel */}
        {selected && (
          <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 px-4" onClick={() => setSelected(null)}>
            <div
              className="bg-brand-surface border border-brand-border rounded-sm p-6 max-w-lg w-full relative"
              onClick={(e) => e.stopPropagation()}
            >
              <button
                onClick={() => setSelected(null)}
                className="absolute top-4 right-4 text-brand-muted hover:text-brand-text"
              >
                <X className="w-4 h-4" />
              </button>
              <div className="font-mono text-[10px] text-brand-muted uppercase tracking-widest mb-2">Worker Detail</div>
              <h2 className="font-heading font-bold text-brand-text text-xl mb-2">{selected.name}</h2>
              <p className="text-brand-muted font-mono text-sm leading-relaxed mb-4">{selected.description}</p>
              <div className="mb-4">
                <div className="text-[10px] font-mono text-brand-muted uppercase tracking-widest mb-2">Tools Used</div>
                <div className="flex flex-wrap gap-1.5">
                  {selected.tools.map((t) => (
                    <span key={t} className="text-xs font-mono bg-brand-bg border border-brand-border text-brand-muted px-2 py-1 rounded-sm">
                      {t}
                    </span>
                  ))}
                </div>
              </div>
              <div className="mb-4">
                <div className="text-[10px] font-mono text-brand-muted uppercase tracking-widest mb-2">Sample Output</div>
                <pre className="text-xs font-mono text-brand-muted bg-brand-bg border border-brand-border rounded-sm p-3 whitespace-pre-wrap">
{`{
  "worker": "${selected.name}",
  "status": "completed",
  "confidence": 0.97,
  "action": "Bill created in ERP",
  "audit_id": "audit-${Math.random().toString(36).slice(2, 8)}",
  "duration_ms": 1840
}`}
                </pre>
              </div>
              <div className="flex gap-2">
                <button className="flex-1 bg-brand-green text-black font-mono font-semibold text-xs py-2 rounded-sm hover:bg-[#00a844] transition-colors">
                  Deploy This Worker
                </button>
                <button
                  onClick={() => setSelected(null)}
                  className="text-xs font-mono text-brand-muted border border-brand-border px-4 py-2 rounded-sm hover:text-brand-text transition-colors"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
      <Footer />
    </>
  );
}
