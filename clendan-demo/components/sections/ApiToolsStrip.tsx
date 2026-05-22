import Link from "next/link";
import { API_TOOLS } from "@/lib/constants";

export function ApiToolsStrip() {
  return (
    <section className="py-24 px-6 border-t border-brand-border">
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-14">
          <p className="text-[10px] font-mono text-brand-muted uppercase tracking-widest mb-3">Standalone APIs</p>
          <h2 className="font-heading text-3xl md:text-4xl font-bold text-brand-text">
            5 APIs. Use Them Inside Clendan or On Their Own.
          </h2>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {API_TOOLS.map((tool) => (
            <div
              key={tool.id}
              className="bg-brand-surface border border-brand-border rounded-sm p-5 flex flex-col gap-3"
            >
              <div>
                <div className="font-heading font-semibold text-brand-text text-sm mb-1">{tool.name}</div>
                <div className="font-mono text-xs text-brand-green bg-[rgba(0,200,83,0.06)] border border-[rgba(0,200,83,0.15)] px-2 py-1 rounded-sm inline-block">
                  {tool.endpoint}
                </div>
              </div>
              <p className="text-brand-muted text-xs font-mono leading-relaxed flex-1">{tool.description}</p>
              <Link
                href="/api-tools"
                className="text-xs font-mono text-brand-muted border border-brand-border px-3 py-1.5 rounded-sm hover:text-brand-text hover:border-brand-text transition-colors self-start"
              >
                Try It →
              </Link>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
