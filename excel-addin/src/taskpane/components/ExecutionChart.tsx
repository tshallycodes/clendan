import React, { useEffect, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { styles } from "../styles";

const API_BASE = "https://api.clendan.com";

interface ToolStats {
  total: number;
  auto_approved: number;
  pending: number;
  blocked: number;
}

interface ChartPoint {
  name: string;
  approved: number;
  pending: number;
  blocked: number;
}

interface ExecutionChartProps {
  apiKey: string;
}

export default function ExecutionChart({ apiKey }: ExecutionChartProps): React.ReactElement {
  const [data, setData] = useState<ChartPoint[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    if (!apiKey) {
      setLoading(false);
      return;
    }

    let cancelled = false;

    async function load(): Promise<void> {
      try {
        const response = await fetch(`${API_BASE}/v1/execute/stats`, {
          headers: { Authorization: `Bearer ${apiKey}` },
        });

        if (!response.ok) {
          throw new Error(`${response.status}`);
        }

        const body = await response.json();
        if (body.error) throw new Error(body.error);

        const byTool: Record<string, ToolStats> = body.data?.by_tool ?? {};

        const points: ChartPoint[] = Object.entries(byTool)
          .filter(([, s]) => s.total > 0)
          .map(([key, s]) => ({
            name: key.replace(/_/g, " "),
            approved: s.auto_approved,
            pending: s.pending,
            blocked: s.blocked,
          }));

        if (!cancelled) {
          setData(points);
          setError("");
        }
      } catch (err) {
        if (!cancelled) {
          setError("Could not load chart data");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [apiKey]);

  if (loading) {
    return (
      <div style={styles.dashboardSection}>
        <p style={styles.label}>EXECUTION BREAKDOWN</p>
        <p style={{ ...styles.label, opacity: 0.5 }}>Loading…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={styles.dashboardSection}>
        <p style={styles.label}>EXECUTION BREAKDOWN</p>
        <p style={styles.errorText}>{error}</p>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div style={styles.dashboardSection}>
        <p style={styles.label}>EXECUTION BREAKDOWN</p>
        <p style={{ ...styles.label, opacity: 0.4 }}>No executions yet</p>
      </div>
    );
  }

  return (
    <div style={styles.dashboardSection}>
      <div style={styles.divider} />
      <p style={styles.label}>EXECUTION BREAKDOWN</p>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart
          data={data}
          margin={{ top: 4, right: 4, left: -20, bottom: 0 }}
          barSize={8}
        >
          <XAxis
            dataKey="name"
            tick={{ fontSize: 8, fill: "#4a6a4a" }}
            interval={0}
            angle={-25}
            textAnchor="end"
            height={40}
          />
          <YAxis tick={{ fontSize: 8, fill: "#4a6a4a" }} />
          <Tooltip
            contentStyle={{
              background: "#111111",
              border: "1px solid #1a2a1a",
              color: "#e8f0e8",
              fontSize: 11,
              fontFamily: "'IBM Plex Mono', monospace",
            }}
          />
          <Legend
            wrapperStyle={{ fontSize: 9, color: "#a0b8a0", paddingTop: 4 }}
          />
          <Bar dataKey="approved" stackId="a" fill="#00C853" name="Approved" />
          <Bar dataKey="pending" stackId="a" fill="#00a8cc" name="Pending" />
          <Bar dataKey="blocked" stackId="a" fill="#ff4d6d" name="Blocked" radius={[2, 2, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
