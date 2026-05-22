"use client";

import { motion } from "framer-motion";
import { useInView } from "framer-motion";
import { useRef } from "react";
import { WorkerCard } from "@/components/ui/WorkerCard";
import { WORKERS } from "@/lib/constants";

export function WorkerShowcase() {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-60px" });

  return (
    <section className="py-24 px-6 border-t border-brand-border">
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-14">
          <p className="text-[10px] font-mono text-brand-muted uppercase tracking-widest mb-3">AI Workers</p>
          <h2 className="font-heading text-3xl md:text-4xl font-bold text-brand-text">
            10 AI Workers. Every Finance Function Covered.
          </h2>
        </div>

        <div ref={ref} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {WORKERS.map((worker, i) => (
            <motion.div
              key={worker.id}
              initial={{ opacity: 0, y: 16 }}
              animate={inView ? { opacity: 1, y: 0 } : {}}
              transition={{ delay: i * 0.06, duration: 0.4 }}
            >
              <WorkerCard
                name={worker.name}
                description={worker.description}
                badge={worker.badge}
                tools={worker.tools}
                status={worker.status}
              />
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
