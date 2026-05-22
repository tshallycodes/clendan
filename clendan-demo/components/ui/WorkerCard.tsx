"use client";

import { cn } from "@/lib/utils";

type Badge = "MVP" | "V2" | "V3";
type Status = "active" | "inactive" | "pending";

interface WorkerCardProps {
  name: string;
  description: string;
  badge: Badge;
  tools: string[];
  status?: Status;
  onClick?: () => void;
  className?: string;
}

const BADGE_STYLES: Record<Badge, string> = {
  MVP: "bg-[rgba(0,200,83,0.08)] text-brand-green border border-[rgba(0,200,83,0.2)]",
  V2: "bg-[rgba(0,168,204,0.08)] text-brand-info border border-[rgba(0,168,204,0.2)]",
  V3: "bg-brand-surface text-brand-muted border border-brand-border",
};

const STATUS_BORDER: Record<Status, string> = {
  active: "border-l-brand-green",
  inactive: "",
  pending: "border-l-brand-info",
};

export function WorkerCard({
  name,
  description,
  badge,
  tools,
  status = "inactive",
  onClick,
  className,
}: WorkerCardProps) {
  return (
    <div
      onClick={onClick}
      className={cn(
        "bg-brand-surface border border-brand-border rounded-sm p-4 cursor-pointer",
        "border-l-[3px] transition-all duration-200",
        "hover:-translate-y-0.5 hover:border-brand-green hover:border-l-brand-green",
        status === "active" && STATUS_BORDER[status],
        status !== "active" && "border-l-brand-border",
        className
      )}
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <h3 className="font-heading font-semibold text-brand-text text-sm leading-snug">{name}</h3>
        <span className={cn("text-[10px] font-mono uppercase px-2 py-0.5 rounded-sm shrink-0", BADGE_STYLES[badge])}>
          {badge}
        </span>
      </div>
      <p className="text-brand-muted text-xs leading-relaxed mb-3">{description}</p>
      <div className="flex flex-wrap gap-1">
        {tools.map((tool) => (
          <span
            key={tool}
            className="text-[10px] font-mono text-brand-muted bg-brand-bg border border-brand-border px-2 py-0.5 rounded-sm"
          >
            {tool}
          </span>
        ))}
      </div>
    </div>
  );
}
