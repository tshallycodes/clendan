import React, { useState } from "react";
import { styles } from "../styles";

/* global Excel */

const API_BASE = "https://api.clendan.com";
const SHEET_NAME = "Clendan Analysis";

const TOOLS = [
  "Invoice Processing",
  "Fraud Detection",
  "AI Accountant",
  "Collections",
  "Expense Control",
  "Reconciliation",
  "Revenue Recognition",
  "Compliance Check",
  "Treasury",
];

const TOOL_API_KEYS: Record<string, string> = {
  "Invoice Processing": "invoice_processing",
  "Fraud Detection": "fraud_detection",
  "AI Accountant": "ai_accountant",
  "Collections": "collections",
  "Expense Control": "expense_control",
  "Reconciliation": "reconciliation",
  "Revenue Recognition": "revenue_recognition",
  "Compliance Check": "compliance_check",
  "Treasury": "treasury",
};

const HEADER_ROW = ["Tool", "Executions", "Auto-Approved", "Pending Review", "Blocked"];
const TITLE_CELL = "Clendan — Execution Summary";

interface ToolStats {
  total: number;
  auto_approved: number;
  pending: number;
  blocked: number;
}

interface StatsResponse {
  data: {
    by_tool: Record<string, ToolStats>;
    total_executions: number;
    last_30_days: number;
  };
  error: string | null;
}

interface DashboardGeneratorProps {
  apiKey: string;
}

export default function DashboardGenerator({ apiKey }: DashboardGeneratorProps): React.ReactElement {
  const [generating, setGenerating] = useState<boolean>(false);
  const [done, setDone] = useState<boolean>(false);
  const [doneMessage, setDoneMessage] = useState<string>("");
  const [error, setError] = useState<string>("");

  async function fetchStats(): Promise<StatsResponse> {
    const response = await fetch(`${API_BASE}/v1/execute/stats`, {
      headers: { Authorization: `Bearer ${apiKey}` },
    });
    if (!response.ok) {
      throw new Error(`Stats fetch failed: ${response.statusText}`);
    }
    return response.json() as Promise<StatsResponse>;
  }

  async function handleGenerate(): Promise<void> {
    setGenerating(true);
    setDone(false);
    setError("");

    try {
      const statsBody = await fetchStats();
      const byTool = statsBody.data.by_tool;
      const totalExecutions = statsBody.data.total_executions;

      const dataRows = TOOLS.map((tool) => {
        const apiKey = TOOL_API_KEYS[tool];
        const s = byTool[apiKey];
        return [
          tool,
          s?.total ?? 0,
          s?.auto_approved ?? 0,
          s?.pending ?? 0,
          s?.blocked ?? 0,
        ];
      });

      await Excel.run(async (context) => {
        const sheets = context.workbook.worksheets;
        sheets.load("items/name");
        await context.sync();

        const existing = sheets.items.find((s) => s.name === SHEET_NAME);
        let sheet: Excel.Worksheet;

        if (existing) {
          sheet = existing;
          sheet.activate();
        } else {
          sheet = sheets.add(SHEET_NAME);
          sheet.activate();
        }

        const titleCell = sheet.getRange("A1");
        titleCell.values = [[TITLE_CELL]];
        titleCell.format.font.bold = true;
        titleCell.format.font.size = 14;

        const headerRange = sheet.getRange("A3:E3");
        headerRange.values = [HEADER_ROW];
        headerRange.format.font.bold = true;
        headerRange.format.fill.color = "#111111";

        const dataRange = sheet.getRange(`A4:E${4 + TOOLS.length - 1}`);
        dataRange.values = dataRows;

        sheet.getUsedRange().format.autofitColumns();

        await context.sync();
      });

      setDoneMessage(`Dashboard updated — ${totalExecutions} total executions`);
      setDone(true);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setError(`Could not generate dashboard: ${message}`);
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div style={styles.dashboardSection}>
      <div style={styles.divider} />
      <p style={styles.label}>DASHBOARD</p>
      <button
        onClick={handleGenerate}
        style={{
          ...styles.secondaryButton,
          width: "100%",
          opacity: generating ? 0.5 : 1,
          cursor: generating ? "not-allowed" : "pointer",
        }}
        disabled={generating}
      >
        {generating ? "Generating…" : "Generate Dashboard"}
      </button>

      {done && <p style={styles.successText}>{doneMessage}</p>}
      {error && <p style={styles.errorText}>{error}</p>}
    </div>
  );
}
