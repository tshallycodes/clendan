"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { TERMINAL_LINES } from "@/lib/constants";

interface TerminalLine {
  timestamp: string;
  text: string;
  color: string;
}

interface TerminalWindowProps {
  lines?: TerminalLine[];
  title?: string;
  className?: string;
  autoPlay?: boolean;
  intervalMs?: number;
}

export function TerminalWindow({
  lines = TERMINAL_LINES,
  title = "clendan-orchestrator",
  className,
  autoPlay = true,
  intervalMs = 600,
}: TerminalWindowProps) {
  const [visibleCount, setVisibleCount] = useState(0);
  const [showCursor, setShowCursor] = useState(true);

  useEffect(() => {
    if (!autoPlay) {
      setVisibleCount(lines.length);
      return;
    }
    if (visibleCount >= lines.length) return;
    const timer = setTimeout(() => setVisibleCount((c) => c + 1), intervalMs);
    return () => clearTimeout(timer);
  }, [visibleCount, lines.length, autoPlay, intervalMs]);

  useEffect(() => {
    const cursorTimer = setInterval(() => setShowCursor((v) => !v), 530);
    return () => clearInterval(cursorTimer);
  }, []);

  return (
    <div className={cn("rounded-md border border-brand-border overflow-hidden font-mono text-sm", className)}>
      {/* Title bar */}
      <div className="flex items-center gap-2 px-4 py-3 bg-brand-surface border-b border-brand-border">
        <span className="w-3 h-3 rounded-full bg-[#ff5f57]" />
        <span className="w-3 h-3 rounded-full bg-[#febc2e]" />
        <span className="w-3 h-3 rounded-full bg-[#28c840]" />
        <span className="ml-3 text-brand-muted text-xs tracking-wide">{title}</span>
      </div>

      {/* Content */}
      <div className="bg-[#0d0d14] p-4 min-h-[220px]">
        {lines.slice(0, visibleCount).map((line, i) => (
          <div key={i} className="flex gap-3 mb-1 leading-relaxed">
            <span className="text-brand-muted shrink-0">[{line.timestamp}]</span>
            <span className={line.color}>{line.text}</span>
          </div>
        ))}
        {visibleCount < lines.length || autoPlay ? (
          <div className="flex gap-3 mt-1">
            <span className="text-brand-muted shrink-0">{">"}</span>
            <span
              className={cn(
                "w-2 h-4 bg-brand-green inline-block translate-y-0.5",
                showCursor ? "opacity-100" : "opacity-0"
              )}
            />
          </div>
        ) : null}
      </div>
    </div>
  );
}
