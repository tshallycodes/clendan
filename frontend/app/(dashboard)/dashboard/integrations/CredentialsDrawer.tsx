'use client'

import { useState } from 'react'

interface CredentialField {
  name: string
  label: string
  type: 'text' | 'password' | 'select'
  placeholder?: string
  options?: string[]
}

interface IntegrationCredConfig {
  title: string
  fields: CredentialField[]
}

const CONFIGS: Record<string, IntegrationCredConfig> = {
  gocardless: {
    title: 'GoCardless',
    fields: [
      { name: 'access_token', label: 'Access Token', type: 'password', placeholder: 'live_...' },
      { name: 'environment', label: 'Environment', type: 'select', options: ['sandbox', 'live'] },
    ],
  },
  adyen: {
    title: 'Adyen',
    fields: [
      { name: 'api_key', label: 'API Key', type: 'password', placeholder: 'AQEt...' },
      { name: 'merchant_account', label: 'Merchant Account', type: 'text', placeholder: 'YourCompany_TEST' },
      { name: 'environment', label: 'Environment', type: 'select', options: ['test', 'live'] },
    ],
  },
  wise: {
    title: 'Wise',
    fields: [
      { name: 'api_token', label: 'API Token', type: 'password', placeholder: 'paste your Wise API token' },
      { name: 'environment', label: 'Environment', type: 'select', options: ['sandbox', 'live'] },
    ],
  },
  netsuite: {
    title: 'NetSuite',
    fields: [
      { name: 'account_id', label: 'Account ID', type: 'text', placeholder: '1234567' },
      { name: 'consumer_key', label: 'Consumer Key', type: 'password', placeholder: '' },
      { name: 'consumer_secret', label: 'Consumer Secret', type: 'password', placeholder: '' },
      { name: 'token_id', label: 'Token ID', type: 'password', placeholder: '' },
      { name: 'token_secret', label: 'Token Secret', type: 'password', placeholder: '' },
    ],
  },
  sap: {
    title: 'SAP',
    fields: [
      { name: 'base_url', label: 'Service URL', type: 'text', placeholder: 'https://...' },
      { name: 'client_id', label: 'Client ID', type: 'text', placeholder: '' },
      { name: 'client_secret', label: 'Client Secret', type: 'password', placeholder: '' },
    ],
  },
  'sage-intacct': {
    title: 'Sage Intacct',
    fields: [
      { name: 'sender_id', label: 'Sender ID', type: 'text', placeholder: '' },
      { name: 'sender_password', label: 'Sender Password', type: 'password', placeholder: '' },
      { name: 'company_id', label: 'Company ID', type: 'text', placeholder: '' },
      { name: 'user_id', label: 'User ID', type: 'text', placeholder: '' },
      { name: 'user_password', label: 'User Password', type: 'password', placeholder: '' },
    ],
  },
}

interface Props {
  slug: string | null
  open: boolean
  onClose: () => void
  onSubmit: (slug: string, credentials: Record<string, string>) => Promise<void>
}

export function CredentialsDrawer({ slug, open, onClose, onSubmit }: Props) {
  const [values, setValues] = useState<Record<string, string>>({})
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const cfg = slug ? CONFIGS[slug] : null

  function handleClose() {
    setValues({})
    setError(null)
    onClose()
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!slug || !cfg) return
    setError(null)
    setSubmitting(true)
    try {
      const filled: Record<string, string> = {}
      for (const f of cfg.fields) {
        filled[f.name] = f.type === 'select'
          ? (values[f.name] ?? f.options?.[0] ?? '')
          : (values[f.name] ?? '')
      }
      await onSubmit(slug, filled)
      setValues({})
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Connection failed')
    } finally {
      setSubmitting(false)
    }
  }

  if (!open || !cfg) return null

  return (
    <div className="fixed inset-0 z-50 flex justify-end" onClick={(e) => { if (e.target === e.currentTarget) handleClose() }}>
      <div className="w-full max-w-sm bg-brand-surface border-l border-brand-border h-full flex flex-col shadow-2xl">
        <div className="flex items-center justify-between px-5 py-4 border-b border-brand-border">
          <h2 className="text-sm font-mono font-medium text-brand-text">Connect {cfg.title}</h2>
          <button type="button" onClick={handleClose} className="text-brand-muted hover:text-brand-text transition-colors text-lg leading-none">×</button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4 p-5 flex-1 overflow-y-auto">
          {cfg.fields.map((field) => (
            <label key={field.name} className="flex flex-col gap-1.5">
              <span className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">{field.label}</span>
              {field.type === 'select' ? (
                <select
                  value={values[field.name] ?? field.options?.[0] ?? ''}
                  onChange={(e) => setValues((v) => ({ ...v, [field.name]: e.target.value }))}
                  className="bg-brand-bg border border-brand-border focus:border-[#00C853] text-brand-text rounded-sm px-3 py-2 text-xs font-mono outline-none transition-colors"
                >
                  {field.options?.map((o) => <option key={o} value={o}>{o}</option>)}
                </select>
              ) : (
                <input
                  type={field.type}
                  value={values[field.name] ?? ''}
                  onChange={(e) => setValues((v) => ({ ...v, [field.name]: e.target.value }))}
                  placeholder={field.placeholder}
                  autoComplete="off"
                  required
                  className="bg-brand-bg border border-brand-border focus:border-[#00C853] text-brand-text rounded-sm px-3 py-2 text-xs font-mono outline-none placeholder-brand-muted transition-colors"
                />
              )}
            </label>
          ))}

          {error && (
            <p className="text-[10px] font-mono text-[#ff4d6d] bg-[rgba(255,77,109,0.08)] border border-[rgba(255,77,109,0.2)] rounded-sm px-3 py-2">
              {error}
            </p>
          )}

          <div className="flex gap-2 mt-auto pt-4">
            <button
              type="submit"
              disabled={submitting}
              className="flex-1 text-xs font-mono bg-[#00C853] text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-3 py-2 transition-all disabled:opacity-50"
            >
              {submitting ? 'Connecting...' : 'Connect'}
            </button>
            <button
              type="button"
              onClick={handleClose}
              className="text-xs font-mono border border-brand-border text-brand-muted rounded-sm px-3 py-2 hover:text-brand-text transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
