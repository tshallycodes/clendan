import React, { useState } from "react";
import { styles } from "../styles";

/* global Excel, crypto */

const API_BASE = "https://api.clendan.com";

export interface RunResult {
  execution_id: string;
  status: string;
  decision: string;
  tool: string;
  idempotent?: boolean;
}

interface RangeRunnerProps {
  tool: string;
  apiKey: string;
  onResult: (r: RunResult) => void;
  onError: (e: string) => void;
}

interface ApiResponse {
  data: RunResult;
  error: string | null;
  trace_id: string;
  timestamp: string;
}

export default function RangeRunner({
  tool,
  apiKey,
  onResult,
  onError,
}: RangeRunnerProps): React.ReactElement {
  const [rangeAddress, setRangeAddress] = useState<string>("");
  const [rangeValues, setRangeValues] = useState<unknown[][]>([]);
  const [running, setRunning] = useState<boolean>(false);

  async function handleGetSelection(): Promise<void> {
    try {
      await Excel.run(async (ctx) => {
        const range = ctx.workbook.getSelectedRange();
        range.load(["address", "values"]);
        await ctx.sync();
        setRangeAddress(range.address);
        setRangeValues(range.values as unknown[][]);
      });
    } catch (err) {
      onError("Could not read selection. Make sure a range is selected.");
    }
  }

  async function handleRunTool(): Promise<void> {
    if (!rangeAddress || running) return;

    setRunning(true);

    try {
      const idempotencyKey = crypto.randomUUID();

      const response = await fetch(`${API_BASE}/v1/execute`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${apiKey}`,
          "Idempotency-Key": idempotencyKey,
        },
        body: JSON.stringify({
          worker: tool,
          payload: {
            range_data: rangeValues,
            range_address: rangeAddress,
          },
        }),
      });

      if (!response.ok) {
        const errBody = await response.json().catch(() => ({ error: "Unexpected error" }));
        const message = (errBody as { error?: string }).error ?? "Request failed";
        onError(message);
        return;
      }

      const body = (await response.json()) as ApiResponse;

      if (body.error) {
        onError(body.error);
        return;
      }

      onResult(body.data);
    } catch (err) {
      onError("Network error — check your connection and try again.");
    } finally {
      setRunning(false);
    }
  }

  const canRun = Boolean(rangeAddress) && !running;

  return (
    <div style={styles.section}>
      <p style={styles.label}>RANGE</p>

      <div style={styles.rangeRow}>
        <span style={styles.rangeAddress}>
          {rangeAddress || "No range selected"}
        </span>
        <button
          onClick={handleGetSelection}
          style={styles.secondaryButton}
          disabled={running}
        >
          Select
        </button>
      </div>

      <button
        onClick={handleRunTool}
        style={{
          ...styles.primaryButton,
          opacity: canRun ? 1 : 0.4,
          cursor: canRun ? "pointer" : "not-allowed",
        }}
        disabled={!canRun}
      >
        {running ? "Running…" : "Run Tool"}
      </button>
    </div>
  );
}
