import Link from "next/link";

export function CtaBanner() {
  return (
    <section className="py-24 px-6 border-t border-brand-border">
      <div className="max-w-7xl mx-auto">
        {/* Testimonials */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-24">
          {[
            {
              quote: "We cut invoice processing time from 4 days to 40 minutes. Clendan handles everything our finance team used to do manually.",
              name: "Sarah Chen",
              title: "CFO, Orbital Labs",
            },
            {
              quote: "The audit trail is the killer feature. Every decision, every amount, every approval — logged and searchable. Auditors love it.",
              name: "James Whitfield",
              title: "Finance Director, Apex Cloud",
            },
            {
              quote: "Month-end close went from 6 days to 1 day. The AI Accountant Worker is essentially a staff member now.",
              name: "Priya Nair",
              title: "VP Finance, Stackwell",
            },
          ].map((t) => (
            /* REPLACE WITH REAL TESTIMONIALS */
            <div key={t.name} className="bg-brand-surface border border-brand-border rounded-sm p-5">
              <p className="text-brand-text text-sm font-mono leading-relaxed mb-4">"{t.quote}"</p>
              <div className="font-heading font-semibold text-brand-text text-sm">{t.name}</div>
              <div className="text-brand-muted text-xs font-mono">{t.title}</div>
            </div>
          ))}
        </div>

        {/* CTA banner */}
        <div className="bg-[rgba(0,200,83,0.04)] border border-[rgba(0,200,83,0.15)] rounded-sm px-8 py-14 text-center">
          <h2 className="font-heading text-3xl md:text-4xl font-bold text-brand-text mb-3">
            Ready to Automate Your Finance Stack?
          </h2>
          <p className="text-brand-muted font-mono text-sm mb-8">
            Deploy your first AI worker in under 10 minutes.
          </p>
          <Link
            href="#"
            className="inline-block bg-brand-green text-black font-mono font-semibold text-sm px-8 py-3 rounded-sm hover:bg-[#00a844] transition-colors active:scale-[0.97]"
          >
            Request Early Access
          </Link>
        </div>
      </div>
    </section>
  );
}
