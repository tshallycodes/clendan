"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { MOCK_CHART_DATA } from "@/lib/mock-data";

const CustomTooltip = ({ active, payload, label }: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
}) => {
  if (!active || !payload) return null;
  return (
    <div className="bg-brand-elevated border border-brand-border rounded-sm px-3 py-2 font-mono text-xs">
      <div className="text-brand-muted mb-1">{label}</div>
      {payload.map((p) => (
        <div key={p.name} style={{ color: p.color }}>
          {p.name}: {p.value}
        </div>
      ))}
    </div>
  );
};

export function ExecutionChart() {
  return (
    <div className="bg-brand-surface border border-brand-border rounded-sm p-5">
      <div className="flex items-center justify-between mb-6">
        <h3 className="font-heading font-semibold text-brand-text text-sm">Execution Activity</h3>
        <span className="text-xs font-mono text-brand-muted">Last 7 days</span>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={MOCK_CHART_DATA} margin={{ top: 4, right: 4, bottom: 4, left: -20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1a2a1a" />
          <XAxis
            dataKey="day"
            tick={{ fill: "#4a6a4a", fontSize: 11, fontFamily: "var(--font-ibm-plex-mono)" }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: "#4a6a4a", fontSize: 11, fontFamily: "var(--font-ibm-plex-mono)" }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{ fontSize: 11, fontFamily: "var(--font-ibm-plex-mono)", color: "#4a6a4a" }}
          />
          <Line
            type="monotone"
            dataKey="autoExecuted"
            name="Auto-executed"
            stroke="#00C853"
            strokeWidth={2}
            dot={{ fill: "#00C853", r: 3 }}
            activeDot={{ r: 5 }}
          />
          <Line
            type="monotone"
            dataKey="approvalRequired"
            name="Approval required"
            stroke="#00a8cc"
            strokeWidth={2}
            dot={{ fill: "#00a8cc", r: 3 }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
