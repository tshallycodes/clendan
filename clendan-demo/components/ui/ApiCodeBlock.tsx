"use client";

import { useState } from "react";
import { Copy, Check } from "lucide-react";
import { cn } from "@/lib/utils";

type Language = "python" | "nodejs" | "curl";

interface ApiCodeBlockProps {
  samples: Partial<Record<Language, string>>;
  className?: string;
}

const LANG_LABELS: Record<Language, string> = {
  python: "Python",
  nodejs: "Node.js",
  curl: "cURL",
};

function highlight(code: string): React.ReactNode[] {
  const lines = code.split("\n");
  return lines.map((line, i) => {
    const parts = line
      .replace(/(#.*)$/g, '<comment>$1</comment>')
      .replace(/("(?:[^"\\]|\\.)*")/g, '<string>$1</string>')
      .replace(/('(?:[^'\\]|\\.)*')/g, '<string>$1</string>')
      .replace(/\b(import|from|def|async|await|const|let|require|fetch|curl|POST|GET)\b/g, '<keyword>$1</keyword>');
    return (
      <div key={i} dangerouslySetInnerHTML={{ __html: parts
        .replace(/<comment>(.*?)<\/comment>/g, '<span style="color:#4a6a4a">$1</span>')
        .replace(/<string>(.*?)<\/string>/g, '<span style="color:#f5a623">$1</span>')
        .replace(/<keyword>(.*?)<\/keyword>/g, '<span style="color:#00C853">$1</span>')
      }} />
    );
  });
}

export function ApiCodeBlock({ samples, className }: ApiCodeBlockProps) {
  const availableLangs = Object.keys(samples) as Language[];
  const [activeTab, setActiveTab] = useState<Language>(availableLangs[0]);
  const [copied, setCopied] = useState(false);

  const code = samples[activeTab] ?? "";

  function handleCopy() {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className={cn("bg-brand-bg border border-brand-border rounded-sm overflow-hidden", className)}>
      <div className="flex items-center justify-between border-b border-brand-border px-4 py-2">
        <div className="flex gap-1">
          {availableLangs.map((lang) => (
            <button
              key={lang}
              onClick={() => setActiveTab(lang)}
              className={cn(
                "text-xs font-mono px-3 py-1 rounded-sm transition-colors",
                activeTab === lang
                  ? "bg-brand-surface text-brand-text"
                  : "text-brand-muted hover:text-brand-text"
              )}
            >
              {LANG_LABELS[lang]}
            </button>
          ))}
        </div>
        <button
          onClick={handleCopy}
          className="text-brand-muted hover:text-brand-text transition-colors p-1"
          aria-label="Copy code"
        >
          {copied ? <Check className="w-3.5 h-3.5 text-brand-green" /> : <Copy className="w-3.5 h-3.5" />}
        </button>
      </div>
      <pre className="text-xs font-mono p-4 overflow-x-auto leading-relaxed text-brand-text">
        <code>{highlight(code)}</code>
      </pre>
    </div>
  );
}
