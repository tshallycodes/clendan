import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";

/* global Office, document */

Office.onReady(() => {
  const container = document.getElementById("root");
  if (!container) {
    throw new Error("Root element not found");
  }
  const root = createRoot(container);
  root.render(<App />);
});
