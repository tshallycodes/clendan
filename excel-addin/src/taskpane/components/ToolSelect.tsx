import React from "react";
import { styles } from "../styles";

interface ToolSelectProps {
  value: string;
  onChange: (v: string) => void;
}

interface ToolOption {
  value: string;
  label: string;
}

const TOOLS: ToolOption[] = [
  { value: "invoice_processing", label: "Invoice Processing" },
  { value: "fraud_detection", label: "Fraud Detection" },
  { value: "ai_accountant", label: "AI Accountant" },
  { value: "collections", label: "Collections" },
  { value: "expense_control", label: "Expense Control" },
  { value: "reconciliation", label: "Reconciliation" },
  { value: "revenue_recognition", label: "Revenue Recognition" },
  { value: "compliance_check", label: "Compliance Check" },
  { value: "treasury", label: "Treasury" },
];

export default function ToolSelect({ value, onChange }: ToolSelectProps): React.ReactElement {
  return (
    <div style={styles.section}>
      <label style={styles.label} htmlFor="tool-select">
        TOOL
      </label>
      <select
        id="tool-select"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={styles.select}
      >
        {TOOLS.map((tool) => (
          <option key={tool.value} value={tool.value}>
            {tool.label}
          </option>
        ))}
      </select>
    </div>
  );
}
