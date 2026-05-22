"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

interface StatCardProps {
  value: number | string;
  label: string;
  change?: string;
  changeDirection?: "up" | "down" | "neutral";
  prefix?: string;
  suffix?: string;
  animate?: boolean;
}

function useCountUp(target: number, duration = 1200) {
  const [count, setCount] = useState(0);
  const startTime = useRef<number | null>(null);
  const raf = useRef<number>(0);

  useEffect(() => {
    startTime.current = null;
    const step = (timestamp: number) => {
      if (!startTime.current) startTime.current = timestamp;
      const progress = Math.min((timestamp - startTime.current) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setCount(Math.floor(eased * target));
      if (progress < 1) {
        raf.current = requestAnimationFrame(step);
      } else {
        setCount(target);
      }
    };
    raf.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf.current);
  }, [target, duration]);

  return count;
}

export function StatCard({
  value,
  label,
  change,
  changeDirection = "neutral",
  prefix = "",
  suffix = "",
  animate = true,
}: StatCardProps) {
  const numericValue = typeof value === "number" ? value : null;
  const displayCount = useCountUp(animate && numericValue !== null ? numericValue : 0);

  const displayValue =
    numericValue !== null && animate
      ? `${prefix}${displayCount}${suffix}`
      : `${prefix}${value}${suffix}`;

  return (
    <div className="bg-brand-surface border border-brand-border rounded-sm p-4">
      <div className="font-heading text-3xl font-bold text-brand-text mb-1">{displayValue}</div>
      <div className="text-brand-muted text-xs font-mono uppercase tracking-widest mb-2">{label}</div>
      {change && (
        <div
          className={cn(
            "text-xs font-mono",
            changeDirection === "up" && "text-brand-green",
            changeDirection === "down" && "text-brand-danger",
            changeDirection === "neutral" && "text-brand-muted"
          )}
        >
          {changeDirection === "up" && "↑ "}
          {changeDirection === "down" && "↓ "}
          {change}
        </div>
      )}
    </div>
  );
}
