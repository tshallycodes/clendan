"use client";

import { useState, useEffect, useRef } from "react";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { TerminalWindow } from "@/components/ui/TerminalWindow";
import { HOW_IT_WORKS_STEPS } from "@/lib/constants";
import { cn } from "@/lib/utils";

export default function HowItWorksPage() {
  const [activeStep, setActiveStep] = useState(0);
  const stepRefs = useRef<(HTMLDivElement | null)[]>([]);

  useEffect(() => {
    const observers = stepRefs.current.map((ref, i) => {
      if (!ref) return null;
      const observer = new IntersectionObserver(
        ([entry]) => { if (entry.isIntersecting) setActiveStep(i); },
        { rootMargin: "-40% 0px -40% 0px" }
      );
      observer.observe(ref);
      return observer;
    });
    return () => observers.forEach((o) => o?.disconnect());
  }, []);

  return (
    <>
      <Navbar />
      <main className="pt-20 min-h-screen">
        {/* Hero */}
        <div className="max-w-4xl mx-auto px-6 py-20 text-center border-b border-brand-border">
          <p className="text-[10px] font-mono text-brand-muted uppercase tracking-widest mb-3">How It Works</p>
          <h1 className="font-heading text-4xl md:text-5xl font-extrabold text-brand-text mb-4">
            From Invoice to Audit Log in Seconds
          </h1>
          <p className="text-brand-muted font-mono text-sm max-w-xl mx-auto">
            Clendan orchestrates your entire finance operation. Here is exactly how it works.
          </p>
        </div>

        {/* Scrollable steps */}
        <div className="max-w-7xl mx-auto px-6 py-24 flex gap-12 relative">
          {/* Sticky progress indicator */}
          <div className="hidden lg:flex flex-col items-center gap-0 sticky top-32 self-start h-fit">
            {HOW_IT_WORKS_STEPS.map((step, i) => (
              <div key={step.number} className="flex flex-col items-center">
                <div
                  className={cn(
                    "w-8 h-8 rounded-sm border flex items-center justify-center font-mono text-xs transition-all duration-300",
                    i === activeStep
                      ? "border-brand-green bg-brand-green text-black font-bold"
                      : i < activeStep
                      ? "border-brand-green text-brand-green"
                      : "border-brand-border text-brand-muted"
                  )}
                >
                  {step.number}
                </div>
                {i < HOW_IT_WORKS_STEPS.length - 1 && (
                  <div
                    className={cn(
                      "w-px h-16 transition-colors duration-500",
                      i < activeStep ? "bg-brand-green" : "bg-brand-border"
                    )}
                  />
                )}
              </div>
            ))}
          </div>

          {/* Steps content */}
          <div className="flex-1 space-y-32">
            {HOW_IT_WORKS_STEPS.map((step, i) => (
              <div
                key={step.number}
                ref={(el) => { stepRefs.current[i] = el; }}
                className="min-h-[60vh] flex flex-col justify-center"
              >
                <div className="text-[10px] font-mono text-brand-muted uppercase tracking-widest mb-2">
                  Step {step.number}
                </div>
                <h2 className="font-heading text-3xl md:text-4xl font-bold text-brand-text mb-4">{step.title}</h2>
                <p className="font-mono text-brand-muted text-sm mb-3 max-w-xl leading-relaxed">{step.description}</p>
                <p className="font-mono text-brand-text text-xs max-w-xl leading-relaxed mb-8">{step.detail}</p>
                {i === 3 && (
                  <TerminalWindow className="max-w-lg" />
                )}
              </div>
            ))}
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}
