import React, { useState } from "react";
import { styles } from "../styles";
import type { RunResult } from "./RangeRunner";

/* global navigator */

const DASHBOARD_URL = "https://app.clendan.com/executions";
const EXECUTION_ID_DISPLAY_LENGTH = 12;

interface ResultsPanelProps {
  result: RunResult | null;
  onDismiss: () => void;
}

interface StatusStyle {
  background: string;
  color: string;
  border: string;
  label: string;
}

function getStatusStyle(status: string): StatusStyle {
  if (status === "auto_approved") {
    return {
      background: "rgba(0,200,83,0.08)",
      color: "#00C853",
      border: "1px solid rgba(0,200,83,0.2)",
      label: "Auto Approved",
    };
  }
  if (status === "approval_required") {
    return {
      background: "rgba(0,168,204,0.08)",
      color: "#00a8cc",
      border: "1px solid rgba(0,168,204,0.2)",
      label: "Approval Required",
    };
  }
  return {
    background: "rgba(255,77,109,0.08)",
    color: "#ff4d6d",
    border: "1px solid rgba(255,77,109,0.2)",
    label: "Blocked",
  };
}

export default function ResultsPanel({
  result,
  onDismiss,
}: ResultsPanelProps): React.ReactElement | null {
  const [copied, setCopied] = useState<boolean>(false);

  if (!result) return null;

  const statusStyle = getStatusStyle(result.status);
  const shortId = result.execution_id.slice(0, EXECUTION_ID_DISPLAY_LENGTH) + "…";

  async function handleCopy(): Promise<void> {
    try {
      await navigator.clipboard.writeText(result.execution_id);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard not available in all Office hosts
    }
  }

  return (
    <div style={styles.resultsCard}>
      <div style={styles.resultsHeader}>
        <span style={styles.resultsSectionLabel}>RESULT</span>
        <button onClick={onDismiss} style={styles.dismissButton}>
          ✕
        </button>
      </div>

      <div
        style={{
          ...styles.statusBadge,
          background: statusStyle.background,
          color: statusStyle.color,
          border: statusStyle.border,
        }}
      >
        {statusStyle.label}
      </div>

      <div style={styles.resultRow}>
        <span style={styles.resultLabel}>Decision</span>
        <span style={styles.resultValue}>{result.decision}</span>
      </div>

      <div style={styles.resultRow}>
        <span style={styles.resultLabel}>Execution ID</span>
        <div style={styles.executionIdRow}>
          <span style={styles.executionId}>{shortId}</span>
          <button onClick={handleCopy} style={styles.copyButton}>
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
      </div>

      {result.idempotent && (
        <div style={styles.idempotentNote}>Idempotent — same result as prior run</div>
      )}

      <a
        href={DASHBOARD_URL}
        target="_blank"
        rel="noreferrer"
        style={styles.dashboardLink}
      >
        View in Dashboard →
      </a>
    </div>
  );
}
