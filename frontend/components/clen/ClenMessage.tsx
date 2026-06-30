'use client'

import { motion } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Components } from 'react-markdown'
import { CodeBlock } from '@/components/dashboard/api/CodeBlock'
import type { ClenMessage as ClenMessageType } from './useClen'

interface Props {
  message: ClenMessageType
}

const mdComponents: Components = {
  p: ({ children }) => (
    <p className="text-xs font-body text-brand-text leading-relaxed mb-2 last:mb-0">{children}</p>
  ),
  strong: ({ children }) => (
    <strong className="font-bold text-brand-text">{children}</strong>
  ),
  em: ({ children }) => (
    <em className="italic text-brand-secondary not-italic">{children}</em>
  ),
  h1: ({ children }) => (
    <h1 className="font-heading font-bold text-sm text-brand-text mt-3 mb-1.5 first:mt-0">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="font-heading font-semibold text-xs text-brand-text mt-3 mb-1 first:mt-0 uppercase tracking-wider">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="font-body font-semibold text-xs text-brand-text mt-2 mb-1 first:mt-0">{children}</h3>
  ),
  ul: ({ children }) => (
    <ul className="my-2 space-y-1 first:mt-0 last:mb-0">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="my-2 space-y-1 first:mt-0 last:mb-0 list-none [counter-reset:list-counter]">{children}</ol>
  ),
  li: ({ children, ...props }) => {
    const isOrdered = (props as { ordered?: boolean }).ordered
    return (
      <li className="flex items-start gap-2 text-xs font-body text-brand-text leading-relaxed">
        <span className={`shrink-0 mt-0.5 text-[11px] ${isOrdered ? 'text-brand-muted [counter-increment:list-counter] before:content-[counter(list-counter)"."]' : 'text-brand-muted'}`}>
          {isOrdered ? null : '→'}
        </span>
        <span>{children}</span>
      </li>
    )
  },
  code: ({ children, className }) => {
    const lang = className?.replace('language-', '') ?? ''
    if (className?.startsWith('language-')) {
      return (
        <div className="my-2 first:mt-0 last:mb-0">
          <CodeBlock lang={lang} code={String(children).replace(/\n$/, '')} />
        </div>
      )
    }
    return (
      <code className="bg-brand-elevated border border-brand-border-subtle rounded-sm px-1 py-0.5 text-[12px] font-body text-[#00a8cc]">
        {children}
      </code>
    )
  },
  pre: ({ children }) => <>{children}</>,
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-brand-border pl-3 my-2 first:mt-0 last:mb-0 text-brand-secondary">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="border-t border-brand-border my-3" />,
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-[#00a8cc] underline underline-offset-2 hover:text-brand-text transition-colors"
    >
      {children}
    </a>
  ),
  table: ({ children }) => (
    <div className="my-2 first:mt-0 last:mb-0 overflow-x-auto">
      <table className="w-full text-[12px] font-body border border-brand-border rounded-sm">{children}</table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="bg-brand-elevated border-b border-brand-border">{children}</thead>
  ),
  tbody: ({ children }) => <tbody className="divide-y divide-brand-border">{children}</tbody>,
  tr: ({ children }) => <tr>{children}</tr>,
  th: ({ children }) => (
    <th className="text-left px-3 py-1.5 text-brand-secondary font-semibold uppercase tracking-wider text-[11px]">{children}</th>
  ),
  td: ({ children }) => (
    <td className="px-3 py-1.5 text-brand-text">{children}</td>
  ),
}

export function ClenMessage({ message }: Props) {
  const isUser = message.role === 'user'

  if (isUser) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.15 }}
        className="group flex justify-end mb-3"
      >
        <div className="relative max-w-[80%]">
          <div className="bg-brand-elevated rounded-sm px-3 py-2 text-xs font-body text-brand-text leading-relaxed">
            {message.content}
          </div>
          <span className="absolute -bottom-4 right-0 text-[12px] font-body text-brand-muted opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
            {formatTime(message.timestamp)}
          </span>
        </div>
      </motion.div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.15 }}
      className="group flex gap-2 mb-3"
    >
      <span
        className="text-brand-green font-body text-xs font-bold mt-0.5 shrink-0 leading-relaxed"
        aria-hidden="true"
      >
        C
      </span>
      <div className="flex-1 min-w-0">
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="mb-2 space-y-1">
            {message.toolCalls.map((tc, i) => (
              <div
                key={i}
                className="flex items-center gap-2 text-[11px] font-body text-brand-muted bg-brand-surface border border-brand-border-subtle rounded-sm px-2 py-1"
              >
                <span className="text-brand-warning">◌</span>
                <span>Checking your data</span>
                <span className="text-brand-border-subtle">·</span>
                <span className="truncate">{tc.tool}</span>
                {tc.result && <span className="ml-auto text-brand-green">✓</span>}
              </div>
            ))}
          </div>
        )}
        {message.content && (
          <div className="min-w-0">
            <ReactMarkdown components={mdComponents} remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
          </div>
        )}
        <span className="block mt-1 text-[12px] font-body text-brand-muted opacity-0 group-hover:opacity-100 transition-opacity">
          {formatTime(message.timestamp)}
        </span>
      </div>
    </motion.div>
  )
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}
