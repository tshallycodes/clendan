"use client";

import Link from "next/link";
import { Home, Bot, CheckSquare, List, Plug, Key, Settings } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { icon: Home, label: "Overview", tab: "overview" },
  { icon: Bot, label: "Workers", tab: "workers" },
  { icon: CheckSquare, label: "Approvals", tab: "approvals", badge: 3 },
  { icon: List, label: "Audit Trail", tab: "audit" },
  { icon: Plug, label: "Integrations", tab: "integrations" },
  { icon: Key, label: "API Keys", tab: "api-keys" },
  { icon: Settings, label: "Settings", tab: "settings" },
];

interface SidebarProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
}

export function Sidebar({ activeTab, onTabChange }: SidebarProps) {
  return (
    <aside className="w-56 shrink-0 bg-brand-surface border-r border-brand-border flex flex-col h-full">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-5 py-4 border-b border-brand-border">
        <span className="w-6 h-6 rounded-sm border border-brand-green flex items-center justify-center font-heading font-bold text-brand-green text-xs">
          C
        </span>
        <span className="font-heading font-bold text-brand-text text-xs tracking-[0.15em] uppercase">
          Clendan
        </span>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4">
        {NAV_ITEMS.map(({ icon: Icon, label, tab, badge }) => (
          <button
            key={tab}
            onClick={() => onTabChange(tab)}
            className={cn(
              "w-full flex items-center gap-3 px-5 py-2.5 text-xs font-mono transition-colors relative",
              activeTab === tab
                ? "text-brand-text bg-brand-elevated"
                : "text-brand-muted hover:text-brand-text hover:bg-brand-elevated/50"
            )}
          >
            {activeTab === tab && (
              <span className="absolute left-0 top-1 bottom-1 w-0.5 bg-brand-green rounded-r-full" />
            )}
            <Icon className="w-4 h-4 shrink-0" />
            <span className="flex-1 text-left">{label}</span>
            {badge && (
              <span className="bg-brand-info text-black text-[10px] font-bold rounded-full w-4 h-4 flex items-center justify-center">
                {badge}
              </span>
            )}
          </button>
        ))}
      </nav>

      {/* Back to site */}
      <div className="p-4 border-t border-brand-border">
        <Link
          href="/"
          className="w-full text-xs font-mono text-brand-muted hover:text-brand-text transition-colors block text-center border border-brand-border px-3 py-2 rounded-sm"
        >
          ← Back to site
        </Link>
      </div>
    </aside>
  );
}
