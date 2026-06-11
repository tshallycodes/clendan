'use client'

import { useState } from 'react'
import { useAuth } from '@clerk/nextjs'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

export interface ClenMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  toolCalls?: Array<{
    tool: string
    input: Record<string, unknown>
    result?: Record<string, unknown>
  }>
  pendingAction?: {
    tool: string
    description: string
    params: Record<string, unknown>
  }
}

export type ClenMode = 'docs' | 'account'

function makeId(): string {
  return Math.random().toString(36).slice(2, 10)
}

export function useClen(mode: ClenMode) {
  const { getToken } = useAuth()
  const [messages, setMessages] = useState<ClenMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isOpen, setIsOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function sendMessage(content: string): Promise<void> {
    const userMsg: ClenMessage = {
      id: makeId(),
      role: 'user',
      content,
      timestamp: new Date(),
    }
    const assistantMsg: ClenMessage = {
      id: makeId(),
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      toolCalls: [],
    }

    setMessages(prev => [...prev, userMsg, assistantMsg])
    setIsLoading(true)
    setError(null)

    try {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (mode === 'account') {
        const token = await getToken()
        if (token) headers['Authorization'] = `Bearer ${token}`
      }

      const history = [...messages, userMsg].slice(-20).map(m => ({
        role: m.role,
        content: m.content,
      }))

      const response = await fetch(`${API_BASE}/v1/clen/chat`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ messages: history, mode }),
      })

      if (!response.ok || !response.body) {
        throw new Error(`Server error: ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const raw = line.slice(6).trim()
          if (raw === '[DONE]') {
            setIsLoading(false)
            return
          }
          try {
            const event = JSON.parse(raw)
            if (event.type === 'text') {
              setMessages(prev => {
                const updated = [...prev]
                const last = updated[updated.length - 1]
                updated[updated.length - 1] = { ...last, content: last.content + event.content }
                return updated
              })
            } else if (event.type === 'tool_call') {
              setMessages(prev => {
                const updated = [...prev]
                const last = updated[updated.length - 1]
                const tc = { tool: event.tool, input: event.input ?? {} }
                updated[updated.length - 1] = {
                  ...last,
                  toolCalls: [...(last.toolCalls ?? []), tc],
                }
                return updated
              })
            } else if (event.type === 'tool_result') {
              setMessages(prev => {
                const updated = [...prev]
                const last = updated[updated.length - 1]
                const toolCalls = (last.toolCalls ?? []).map(tc =>
                  tc.tool === event.tool ? { ...tc, result: event.result } : tc
                )
                updated[updated.length - 1] = { ...last, toolCalls }
                return updated
              })
            }
          } catch {
            /* malformed event — skip */
          }
        }
      }
    } catch {
      setError('Connection failed. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  function clearConversation() {
    setMessages([])
    setError(null)
  }

  return { messages, isLoading, isOpen, setIsOpen, sendMessage, clearConversation, error }
}
