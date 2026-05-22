import { INTEGRATIONS } from "@/lib/constants";

export function IntegrationStrip() {
  return (
    <section className="py-24 px-6 border-t border-brand-border">
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-14">
          <p className="text-[10px] font-mono text-brand-muted uppercase tracking-widest mb-3">Integrations</p>
          <h2 className="font-heading text-3xl md:text-4xl font-bold text-brand-text">
            Plugs Into Your Existing Stack
          </h2>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {Object.entries(INTEGRATIONS).map(([category, tools]) => (
            <div key={category} className="col-span-1">
              <div className="text-[10px] font-mono text-brand-muted uppercase tracking-widest mb-2 border-b border-brand-border pb-1">
                {category}
              </div>
              <div className="flex flex-col gap-1.5">
                {tools.map((tool) => (
                  <div
                    key={tool}
                    className="text-xs font-mono text-brand-text bg-brand-surface border border-brand-border px-2 py-1.5 rounded-sm hover:border-brand-muted transition-colors"
                  >
                    {tool}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
