import React, { useEffect, useState } from "react";
import AuthPanel from "./components/AuthPanel";
import ToolSelect from "./components/ToolSelect";
import RangeRunner from "./components/RangeRunner";
import ResultsPanel from "./components/ResultsPanel";
import DashboardGenerator from "./components/DashboardGenerator";
import ExecutionChart from "./components/ExecutionChart";
import { styles } from "./styles";
import type { RunResult } from "./components/RangeRunner";

const API_KEY_STORAGE_KEY = "clendan_api_key";
const KEY_DISPLAY_LENGTH = 10;
const DEFAULT_TOOL = "invoice_processing";

type AppState = "loading" | "unauthed" | "authed";

function maskApiKey(key: string): string {
  return key.slice(0, KEY_DISPLAY_LENGTH) + "…";
}

export default function App(): React.ReactElement {
  const [appState, setAppState] = useState<AppState>("loading");
  const [apiKey, setApiKey] = useState<string>("");
  const [selectedTool, setSelectedTool] = useState<string>(DEFAULT_TOOL);
  const [result, setResult] = useState<RunResult | null>(null);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    const stored = localStorage.getItem(API_KEY_STORAGE_KEY);
    if (stored && stored.startsWith("ck_live_")) {
      setApiKey(stored);
      setAppState("authed");
    } else {
      setAppState("unauthed");
    }
  }, []);

  function handleAuthed(): void {
    const stored = localStorage.getItem(API_KEY_STORAGE_KEY) ?? "";
    setApiKey(stored);
    setAppState("authed");
  }

  function handleDisconnect(): void {
    localStorage.removeItem(API_KEY_STORAGE_KEY);
    setApiKey("");
    setResult(null);
    setError("");
    setAppState("unauthed");
  }

  function handleResult(r: RunResult): void {
    setResult(r);
    setError("");
  }

  function handleError(e: string): void {
    setError(e);
    setResult(null);
  }

  if (appState === "loading") {
    return <div style={{ background: "#0a0a0a", minHeight: "100vh" }} />;
  }

  if (appState === "unauthed") {
    return <AuthPanel onAuthed={handleAuthed} />;
  }

  return (
    <div style={styles.appShell}>
      <header style={styles.header}>
        <div style={styles.headerLogoMark}>C</div>
        <span style={styles.headerWordmark}>CLENDAN</span>
        <span style={styles.headerKeyHint}>{maskApiKey(apiKey)}</span>
      </header>

      <main style={styles.content}>
        <ToolSelect value={selectedTool} onChange={setSelectedTool} />

        <RangeRunner
          tool={selectedTool}
          apiKey={apiKey}
          onResult={handleResult}
          onError={handleError}
        />

        {error && <p style={styles.errorText}>{error}</p>}

        {result && (
          <ResultsPanel result={result} onDismiss={() => setResult(null)} />
        )}

        <ExecutionChart apiKey={apiKey} />

        <DashboardGenerator apiKey={apiKey} />
      </main>

      <div style={{ padding: "8px 16px 16px", textAlign: "right" }}>
        <button onClick={handleDisconnect} style={styles.disconnectButton}>
          Disconnect
        </button>
      </div>
    </div>
  );
}
