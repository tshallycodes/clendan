"use client";

import { useState } from "react";
import { Check, ChevronDown } from "lucide-react";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { cn } from "@/lib/utils";

const TIERS = [
  {
    name: "Starter",
    price: "£299",
    period: "/month",
    description: "For small finance teams getting started with AI automation.",
    features: [
      "2 AI workers",
      "500 executions/month",
      "QuickBooks + Xero integrations",
      "Basic policy engine",
      "Email support",
      "Audit trail: 30 days",
    ],
    cta: "Get Started",
    highlight: false,
  },
  {
    name: "Growth",
    price: "£799",
    period: "/month",
    description: "For scaling finance teams that need full automation coverage.",
    features: [
      "5 AI workers",
      "5,000 executions/month",
      "All integrations",
      "Advanced policy engine",
      "Standalone API access (10k calls/mo)",
      "Priority support",
      "Audit trail: 1 year",
    ],
    cta: "Start Free Trial",
    highlight: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    period: "",
    description: "For enterprises that need unlimited scale and dedicated support.",
    features: [
      "Unlimited workers",
      "Unlimited executions",
      "Custom integrations",
      "SLA guarantee",
      "Dedicated support",
      "SOC 2 compliance",
      "Audit trail: unlimited",
      "On-premise option",
    ],
    cta: "Contact Sales",
    highlight: false,
  },
];

const FAQS = [
  {
    question: "What counts as an execution?",
    answer: "An execution is a single end-to-end run of an AI worker — from receiving an event to writing the audit log. This includes sub-steps like parsing, policy checks, and ERP writes. One invoice processed = one execution.",
  },
  {
    question: "Can I build my own workers?",
    answer: "Yes. The Clendan Worker SDK lets you define custom workers with your own logic, tools, and policies. They run within the same orchestration framework and benefit from the same audit trail and policy engine.",
  },
  {
    question: "How does the audit trail work?",
    answer: "Every agent action is written to an immutable audit log before the response is returned. Rows are never updated or deleted — only appended. Logs are scoped per tenant and queryable from the dashboard or API.",
  },
  {
    question: "Is my financial data encrypted?",
    answer: "Yes. All data is encrypted in transit (TLS 1.3) and at rest (AES-256). API keys and OAuth tokens are encrypted with tenant-specific keys and never logged. Financial data never appears in application logs.",
  },
  {
    question: "Do you offer a free trial?",
    answer: "The Growth plan includes a 14-day free trial with no credit card required. You get access to all features including 5 AI workers, all integrations, and the full policy engine.",
  },
];

export default function PricingPage() {
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  return (
    <>
      <Navbar />
      <main className="pt-20 min-h-screen">
        {/* Hero */}
        <div className="max-w-4xl mx-auto px-6 py-20 text-center border-b border-brand-border">
          <p className="text-[10px] font-mono text-brand-muted uppercase tracking-widest mb-3">Pricing</p>
          <h1 className="font-heading text-4xl md:text-5xl font-extrabold text-brand-text mb-4">
            Simple, Transparent Pricing
          </h1>
          <p className="text-brand-muted font-mono text-sm max-w-xl mx-auto">
            No hidden fees. No per-seat pricing. Pay for what your AI workers do.
          </p>
        </div>

        {/* Pricing tiers */}
        <div className="max-w-6xl mx-auto px-6 py-16">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {TIERS.map((tier) => (
              <div
                key={tier.name}
                className={cn(
                  "bg-brand-surface border rounded-sm p-6 flex flex-col relative",
                  tier.highlight
                    ? "border-brand-green border-2"
                    : "border-brand-border"
                )}
              >
                {tier.highlight && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-brand-green text-black text-[10px] font-mono font-bold uppercase tracking-widest px-3 py-0.5 rounded-sm">
                    Most Popular
                  </div>
                )}
                <div className="mb-5">
                  <h2 className="font-heading font-bold text-brand-text text-lg mb-1">{tier.name}</h2>
                  <div className="flex items-baseline gap-1 mb-2">
                    <span className="font-heading font-extrabold text-3xl text-brand-text">{tier.price}</span>
                    <span className="font-mono text-brand-muted text-sm">{tier.period}</span>
                  </div>
                  <p className="text-brand-muted font-mono text-xs leading-relaxed">{tier.description}</p>
                </div>

                <ul className="space-y-2.5 flex-1 mb-6">
                  {tier.features.map((f) => (
                    <li key={f} className="flex items-start gap-2 text-xs font-mono text-brand-text">
                      <Check className="w-3.5 h-3.5 text-brand-green shrink-0 mt-0.5" />
                      {f}
                    </li>
                  ))}
                </ul>

                <button
                  className={cn(
                    "w-full text-sm font-mono font-semibold py-2.5 rounded-sm transition-colors active:scale-[0.97]",
                    tier.highlight
                      ? "bg-brand-green text-black hover:bg-[#00a844]"
                      : "border border-brand-border text-brand-text hover:bg-brand-elevated"
                  )}
                >
                  {tier.cta}
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* FAQ */}
        <div className="max-w-3xl mx-auto px-6 py-16 border-t border-brand-border">
          <h2 className="font-heading text-2xl font-bold text-brand-text text-center mb-10">
            Frequently Asked Questions
          </h2>
          <div className="space-y-2">
            {FAQS.map((faq, i) => (
              <div key={i} className="border border-brand-border rounded-sm overflow-hidden">
                <button
                  onClick={() => setOpenFaq(openFaq === i ? null : i)}
                  className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-brand-surface transition-colors"
                >
                  <span className="font-mono text-sm text-brand-text font-semibold">{faq.question}</span>
                  <ChevronDown
                    className={cn(
                      "w-4 h-4 text-brand-muted shrink-0 transition-transform",
                      openFaq === i && "rotate-180"
                    )}
                  />
                </button>
                {openFaq === i && (
                  <div className="px-5 pb-4 font-mono text-xs text-brand-muted leading-relaxed border-t border-brand-border">
                    {faq.answer}
                  </div>
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
