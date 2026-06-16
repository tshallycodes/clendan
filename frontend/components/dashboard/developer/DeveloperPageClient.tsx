'use client'

import { useState } from 'react'
import { Copy, Check, ExternalLink } from 'lucide-react'
import { ApiKeysSection } from '@/components/dashboard/settings/ApiKeysSection'

const BASE_URL = 'https://api.clendan.com/v1'

const QUICK_START = `curl -X POST https://api.clendan.com/v1/execute \\
  -H "Authorization: Bearer ck_live_..." \\
  -H "Idempotency-Key: $(uuidgen)" \\
  -H "Content-Type: application/json" \\
  -d '{"tool": "document_intelligence", "payload": {}}'`

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      aria-label="Copy to clipboard"
      className="shrink-0 text-brand-muted hover:text-brand-text transition-colors"
    >
      {copied ? <Check className="w-4 h-4 text-[#00C853]" /> : <Copy className="w-4 h-4" />}
    </button>
  )
}

function SectionLabel({ children }: { children: string }) {
  return (
    <p className="text-[10px] font-mono uppercase tracking-widest text-brand-muted mb-3">
      {children}
    </p>
  )
}

export function DeveloperPageClient() {
  return (
    <div className="p-6 max-w-2xl space-y-10">
      <div>
        <h1 className="font-heading font-bold text-2xl text-brand-text">Developer</h1>
        <p className="text-brand-secondary text-xs font-mono mt-1">
          Connect external systems to Clendan via API key.
        </p>
      </div>

      <section className="space-y-3">
        <SectionLabel>API Keys</SectionLabel>
        <ApiKeysSection />
      </section>

      <section className="space-y-3">
        <SectionLabel>Base URL</SectionLabel>
        <div className="flex items-center gap-3 bg-brand-bg border border-brand-border rounded-sm px-4 py-3">
          <code className="flex-1 font-mono text-xs text-brand-text">{BASE_URL}</code>
          <CopyButton text={BASE_URL} />
        </div>
      </section>

      <section className="space-y-3">
        <SectionLabel>Quick Start</SectionLabel>
        <div className="flex items-start gap-3 bg-brand-bg border border-brand-border rounded-sm px-4 py-3">
          <pre className="flex-1 font-mono text-xs text-brand-text whitespace-pre-wrap break-all">{QUICK_START}</pre>
          <CopyButton text={QUICK_START} />
        </div>
      </section>

      <section className="space-y-3">
        <SectionLabel>Documentation</SectionLabel>
        <a
          href="https://clendan.mintlify.app"
          target="_blank"
          rel="noopener noreferrer"
          className="bg-brand-surface border border-brand-border rounded-sm p-4 flex items-center justify-between hover:bg-brand-elevated transition-colors"
        >
          <div className="space-y-0.5">
            <p className="text-sm font-mono text-brand-text">API Reference</p>
            <p className="text-xs font-mono text-brand-muted">Full endpoint reference with examples</p>
          </div>
          <ExternalLink className="w-4 h-4 text-brand-muted shrink-0" />
        </a>
      </section>
    </div>
  )
}
