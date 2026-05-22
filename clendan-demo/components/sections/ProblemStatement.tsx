"use client";

import { motion } from "framer-motion";
import { useInView } from "framer-motion";
import { useRef } from "react";

const STATS = [
  {
    stat: "66%",
    label: "of AP teams still process invoices manually",
    source: "Ardent Partners 2025",
  },
  {
    stat: "6+ days",
    label: "is how long 50% of finance teams take to close the books",
    source: "Ledge 2025",
  },
  {
    stat: "$6+",
    label: "to process a single invoice manually — before errors",
    source: "Industry average",
  },
];

const SOLUTION_CARDS = [
  {
    title: "Deploy AI Workers",
    description:
      "Pre-built agents for every finance function. Invoice processing, reconciliation, fraud detection — deploy in minutes, not months.",
  },
  {
    title: "Connect Your Tools",
    description:
      "OAuth into Xero, QuickBooks, Plaid, and Stripe. Clendan never stores credentials. All tokens are encrypted and scoped.",
  },
  {
    title: "Execute With Full Audit",
    description:
      "Every agent action is logged before it is taken. Immutable. Searchable. Exportable. Policy-bound at every step.",
  },
];

export function ProblemStatement() {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-80px" });

  return (
    <>
      {/* Problem section */}
      <section className="py-24 px-6 border-t border-brand-border">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-14">
            <p className="text-[10px] font-mono text-brand-muted uppercase tracking-widest mb-3">The Problem</p>
            <h2 className="font-heading text-3xl md:text-4xl font-bold text-brand-text">
              Finance Operations Are Broken
            </h2>
          </div>

          <div ref={ref} className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {STATS.map((item, i) => (
              <motion.div
                key={item.stat}
                initial={{ opacity: 0, y: 20 }}
                animate={inView ? { opacity: 1, y: 0 } : {}}
                transition={{ delay: i * 0.1, duration: 0.5 }}
                className="bg-brand-surface border border-brand-border rounded-sm p-6"
              >
                <div className="font-heading text-4xl font-extrabold text-brand-green mb-3">{item.stat}</div>
                <p className="text-brand-text text-sm font-mono leading-relaxed mb-3">{item.label}</p>
                <p className="text-brand-muted text-xs font-mono">Source: {item.source}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Solution section */}
      <section className="py-24 px-6 border-t border-brand-border">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-14">
            <p className="text-[10px] font-mono text-brand-muted uppercase tracking-widest mb-3">The Solution</p>
            <h2 className="font-heading text-3xl md:text-4xl font-bold text-brand-text">
              Autonomous Finance, End to End
            </h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {SOLUTION_CARDS.map((card, i) => (
              <div
                key={card.title}
                className="bg-brand-surface border border-brand-border border-l-[3px] border-l-brand-green rounded-sm p-6"
              >
                <div className="text-[10px] font-mono text-brand-muted uppercase tracking-widest mb-2">0{i + 1}</div>
                <h3 className="font-heading font-bold text-brand-text text-base mb-3">{card.title}</h3>
                <p className="text-brand-muted text-xs font-mono leading-relaxed">{card.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works summary */}
      <section className="py-24 px-6 border-t border-brand-border">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-14">
            <h2 className="font-heading text-3xl font-bold text-brand-text">How It Works</h2>
          </div>
          <div className="flex flex-col md:flex-row items-start md:items-center gap-0 md:gap-0 relative">
            {["Connect", "Configure", "Execute", "Monitor"].map((step, i, arr) => (
              <div key={step} className="flex flex-col md:flex-row items-center flex-1">
                <div className="flex flex-col items-center text-center md:text-center px-4 py-4 md:py-0">
                  <div className="w-10 h-10 rounded-sm bg-brand-surface border border-brand-green flex items-center justify-center font-heading font-bold text-brand-green text-sm mb-3">
                    {String(i + 1).padStart(2, "0")}
                  </div>
                  <div className="font-heading font-semibold text-brand-text text-sm mb-1">{step}</div>
                  <div className="text-brand-muted text-xs font-mono max-w-[120px]">
                    {["OAuth your tools in minutes", "Set autonomy level and policies", "Workers run tasks autonomously", "Full audit trail in real time"][i]}
                  </div>
                </div>
                {i < arr.length - 1 && (
                  <div className="hidden md:block flex-1 border-t border-dashed border-brand-border mx-2" />
                )}
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}
