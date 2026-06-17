'use client'

import { useState } from 'react'
import { Check, Copy } from 'lucide-react'
import { Light as SyntaxHighlighter } from 'react-syntax-highlighter'
import python from 'react-syntax-highlighter/dist/esm/languages/hljs/python'
import javascript from 'react-syntax-highlighter/dist/esm/languages/hljs/javascript'
import typescript from 'react-syntax-highlighter/dist/esm/languages/hljs/typescript'
import bash from 'react-syntax-highlighter/dist/esm/languages/hljs/bash'
import json from 'react-syntax-highlighter/dist/esm/languages/hljs/json'
import sql from 'react-syntax-highlighter/dist/esm/languages/hljs/sql'

SyntaxHighlighter.registerLanguage('python', python)
SyntaxHighlighter.registerLanguage('javascript', javascript)
SyntaxHighlighter.registerLanguage('typescript', typescript)
SyntaxHighlighter.registerLanguage('bash', bash)
SyntaxHighlighter.registerLanguage('sh', bash)
SyntaxHighlighter.registerLanguage('curl', bash)
SyntaxHighlighter.registerLanguage('json', json)
SyntaxHighlighter.registerLanguage('sql', sql)

export const HIGHLIGHT_STYLE: Record<string, React.CSSProperties> = {
  hljs:             { background: 'transparent', color: 'var(--brand-secondary)' },
  'hljs-keyword':   { color: '#f5a623' },
  'hljs-built_in':  { color: '#f5a623' },
  'hljs-type':      { color: '#f5a623' },
  'hljs-string':    { color: '#00C853' },
  'hljs-comment':   { color: 'var(--brand-muted)', fontStyle: 'italic' },
  'hljs-number':    { color: '#00a8cc' },
  'hljs-literal':   { color: '#00a8cc' },
  'hljs-title':     { color: '#00a8cc' },
  'hljs-function':  { color: '#00a8cc' },
  'hljs-attr':      { color: '#f5a623' },
  'hljs-attribute': { color: '#f5a623' },
  'hljs-variable':  { color: 'var(--brand-text)' },
  'hljs-params':    { color: 'var(--brand-secondary)' },
  'hljs-operator':  { color: 'var(--brand-muted)' },
}

export const HIGHLIGHTER_CUSTOM_STYLE: React.CSSProperties = {
  background: 'transparent',
  padding: '16px',
  fontSize: '12px',
  margin: 0,
  fontFamily: '"IBM Plex Mono", monospace',
  lineHeight: '1.6',
  overflowX: 'auto',
}

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

  const resolvedLang = lang === 'text' ? 'bash' : lang

  return (
    <div className="relative group rounded-sm border border-brand-border bg-brand-bg overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 border-b border-brand-border bg-brand-elevated">
        <span className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">{lang}</span>
        <button
          onClick={copy}
          className="flex items-center gap-1.5 text-[10px] font-mono text-brand-muted hover:text-brand-text transition-colors"
        >
          {copied ? <Check className="w-3 h-3 text-brand-green" /> : <Copy className="w-3 h-3" />}
          {copied ? 'copied' : 'copy'}
        </button>
      </div>
      <SyntaxHighlighter language={resolvedLang} style={HIGHLIGHT_STYLE} customStyle={HIGHLIGHTER_CUSTOM_STYLE}>
        {code}
      </SyntaxHighlighter>
    </div>
  )
}
