'use client'

import { useState } from 'react'
import { Check, Copy } from 'lucide-react'

interface CodeBlockProps {
  code: string
  lang?: string
}

export function CodeBlock({ code, lang = 'bash' }: CodeBlockProps) {
  const [copied, setCopied] = useState(false)

  async function copy() {
    await navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="relative group rounded-sm border border-brand-border bg-brand-bg overflow-x-auto">
      <div className="flex items-center justify-between px-4 py-2 border-b border-brand-border">
        <span className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">{lang}</span>
        <button
          onClick={copy}
          className="flex items-center gap-1.5 text-[10px] font-mono text-brand-muted hover:text-brand-text transition-colors"
        >
          {copied ? <Check className="w-3 h-3 text-brand-green" /> : <Copy className="w-3 h-3" />}
          {copied ? 'copied' : 'copy'}
        </button>
      </div>
      <pre className="p-4 text-xs font-mono text-brand-text leading-relaxed overflow-x-auto whitespace-pre">{code}</pre>
    </div>
  )
}
