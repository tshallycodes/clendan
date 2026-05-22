"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { TerminalWindow } from "@/components/ui/TerminalWindow";

const INTEGRATIONS = ["Xero", "QuickBooks", "Plaid", "Stripe", "NetSuite", "Salesforce"];

export function Hero() {
  return (
    <section className="relative min-h-screen flex flex-col items-center justify-center pt-24 pb-16 px-6 overflow-hidden">
      {/* Grid background */}
      <div
        className="absolute inset-0 opacity-[0.04] pointer-events-none"
        style={{
          backgroundImage:
            "linear-gradient(#00C853 1px, transparent 1px), linear-gradient(90deg, #00C853 1px, transparent 1px)",
          backgroundSize: "48px 48px",
        }}
      />

      <div className="relative max-w-4xl mx-auto text-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <div className="inline-block text-[10px] font-mono text-brand-green border border-[rgba(0,200,83,0.2)] bg-[rgba(0,200,83,0.04)] px-3 py-1 rounded-sm mb-6 tracking-widest uppercase">
            AI Financial Agent OS
          </div>
          <h1 className="font-heading text-5xl md:text-7xl font-extrabold text-brand-text leading-[1.05] tracking-tight mb-6">
            Your Finance Team,
            <br />
            <span className="text-brand-green">Running on Autopilot</span>
          </h1>
          <p className="text-brand-muted font-mono text-sm md:text-base leading-relaxed max-w-2xl mx-auto mb-10">
            Deploy AI workers that connect to your financial systems, execute tasks autonomously,
            and produce full audit trails for every action.
            <span className="text-brand-text"> Not a dashboard. Execution infrastructure.</span>
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="flex flex-col sm:flex-row items-center justify-center gap-3 mb-14"
        >
          <Link
            href="/dashboard"
            className="bg-brand-green text-black font-mono font-semibold text-sm px-6 py-3 rounded-sm hover:bg-[#00a844] transition-colors active:scale-[0.97] w-full sm:w-auto text-center"
          >
            Deploy Your First Worker
          </Link>
          <Link
            href="/how-it-works"
            className="border border-brand-border text-brand-text font-mono text-sm px-6 py-3 rounded-sm hover:bg-brand-surface transition-colors w-full sm:w-auto text-center"
          >
            See How It Works →
          </Link>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.35 }}
        >
          <TerminalWindow className="max-w-2xl mx-auto text-left" />
        </motion.div>

        {/* Integration logos strip */}
        <div className="mt-16 border-t border-brand-border pt-10">
          <p className="text-brand-muted text-xs font-mono uppercase tracking-widest mb-6">
            Trusted integrations with
          </p>
          <div className="flex flex-wrap items-center justify-center gap-6">
            {INTEGRATIONS.map((name) => (
              <span
                key={name}
                className="text-brand-muted text-sm font-mono font-semibold tracking-wide hover:text-brand-text transition-colors"
              >
                {name}
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
