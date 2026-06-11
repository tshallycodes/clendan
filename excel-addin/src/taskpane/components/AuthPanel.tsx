/* global OfficeRuntime */

import React, { useState } from "react";
import { styles } from "../styles";

interface AuthPanelProps {
  onAuthed: () => void;
}

const API_KEY_PREFIX = "ck_live_";
const API_KEY_STORAGE_KEY = "clendan_api_key";

export default function AuthPanel({ onAuthed }: AuthPanelProps): React.ReactElement {
  const [apiKey, setApiKey] = useState<string>("");
  const [error, setError] = useState<string>("");

  async function handleSubmit(e: React.FormEvent): Promise<void> {
    e.preventDefault();
    setError("");

    if (!apiKey.startsWith(API_KEY_PREFIX)) {
      setError("Invalid API key format. Key must start with ck_live_");
      return;
    }

    localStorage.setItem(API_KEY_STORAGE_KEY, apiKey);
    try {
      await OfficeRuntime.storage.setItem(API_KEY_STORAGE_KEY, apiKey);
    } catch {
      // OfficeRuntime.storage not available in all contexts — ignore
    }
    onAuthed();
  }

  return (
    <div style={styles.authContainer}>
      <div style={styles.logoMark}>C</div>
      <h1 style={styles.authTitle}>CLENDAN</h1>
      <p style={styles.authSubtitle}>AI Financial Agent OS</p>

      <form onSubmit={handleSubmit} style={styles.form}>
        <label style={styles.label} htmlFor="api-key">
          API KEY
        </label>
        <input
          id="api-key"
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder="ck_live_..."
          style={styles.input}
          autoComplete="off"
          spellCheck={false}
        />

        {error && <p style={styles.errorText}>{error}</p>}

        <button type="submit" style={styles.primaryButton} disabled={!apiKey}>
          Connect
        </button>
      </form>

      <p style={styles.helpText}>
        Find your API key at{" "}
        <a
          href="https://app.clendan.com/settings/api"
          target="_blank"
          rel="noreferrer"
          style={styles.link}
        >
          app.clendan.com/settings/api
        </a>
      </p>
    </div>
  );
}
