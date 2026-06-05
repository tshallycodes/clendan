'use client'

import { useState } from 'react'
import { useAuth } from '@clerk/nextjs'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

interface Props {
  initialName: string
}

export function OrgNameForm({ initialName }: Props) {
  const { getToken } = useAuth()
  const [name, setName] = useState(initialName)
  const [status, setStatus] = useState<'idle' | 'saving' | 'success' | 'error'>('idle')
  const [errorMsg, setErrorMsg] = useState('')

  async function handleSave() {
    if (!name.trim() || name.trim() === initialName) return
    setStatus('saving')
    setErrorMsg('')
    try {
      const token = await getToken()
      const res = await fetch(`${API}/v1/tenants/me`, {
        method: 'PATCH',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ name: name.trim() }),
      })
      if (!res.ok) throw new Error(`${res.status}`)
      setStatus('success')
      setTimeout(() => setStatus('idle'), 2000)
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Save failed')
      setStatus('error')
    }
  }

  return (
    <div className="flex items-center gap-3">
      <input
        type="text"
        value={name}
        onChange={(e) => { setName(e.target.value); setStatus('idle') }}
        className="bg-brand-bg border border-brand-border focus:border-brand-green text-brand-text placeholder:text-brand-muted rounded-sm px-3 py-2 text-xs font-mono outline-none w-56"
      />
      <button
        onClick={handleSave}
        disabled={status === 'saving' || !name.trim() || name.trim() === initialName}
        className="bg-brand-green text-black hover:bg-[#00a844] rounded-sm px-4 py-2 text-xs font-mono disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        {status === 'saving' ? 'Saving...' : 'Save'}
      </button>
      {status === 'success' && (
        <span className="text-xs font-mono text-brand-green">Saved</span>
      )}
      {status === 'error' && (
        <span className="text-xs font-mono text-brand-danger">Error: {errorMsg}</span>
      )}
    </div>
  )
}
