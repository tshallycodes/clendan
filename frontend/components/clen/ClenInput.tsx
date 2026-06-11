'use client'

import { useRef, useState, useCallback, type KeyboardEvent, type ChangeEvent } from 'react'

interface Props {
  onSend: (text: string) => void
  disabled: boolean
}

export function ClenInput({ onSend, disabled }: Props) {
  const [text, setText] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const resize = useCallback(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    const lineH = 20
    const maxH = lineH * 3 + 16
    el.style.height = Math.min(el.scrollHeight, maxH) + 'px'
  }, [])

  function handleChange(e: ChangeEvent<HTMLTextAreaElement>) {
    setText(e.target.value)
    resize()
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  function submit() {
    const trimmed = text.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setText('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  const canSend = text.trim().length > 0 && !disabled

  return (
    <div className="flex items-end gap-2 p-3 border-t border-brand-border">
      <textarea
        ref={textareaRef}
        value={text}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        placeholder="Ask Clen anything..."
        rows={1}
        disabled={disabled}
        className="flex-1 resize-none bg-brand-bg border border-brand-border focus:border-brand-green focus:outline-none rounded-sm px-3 py-2 text-xs font-mono text-brand-text placeholder:text-brand-muted transition-colors leading-5 min-h-[36px] disabled:opacity-50"
      />
      <button
        onClick={submit}
        disabled={!canSend}
        aria-label="Send message"
        className={[
          'shrink-0 w-8 h-8 rounded-sm flex items-center justify-center transition-all active:scale-95 disabled:opacity-30 disabled:cursor-not-allowed',
          canSend ? 'bg-brand-green' : 'bg-brand-elevated',
        ].join(' ')}
      >
        <ArrowUp className={canSend ? 'text-black' : 'text-brand-muted'} />
      </button>
    </div>
  )
}

function ArrowUp({ className }: { className: string }) {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true" className={className}>
      <path d="M7 11V3M3 7l4-4 4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
