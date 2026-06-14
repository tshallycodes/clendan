'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { XeroOrg } from './types'

interface XeroOrgModalProps {
  open: boolean
  orgs: XeroOrg[]
  onConfirm: (xeroTenantId: string) => Promise<void>
  onClose: () => void
}

export function XeroOrgModal({ open, orgs, onConfirm, onClose }: XeroOrgModalProps) {
  const [selected, setSelected] = useState<string | null>(orgs[0]?.xero_tenant_id ?? null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleConfirm() {
    if (!selected) return
    setError(null)
    setLoading(true)
    try {
      await onConfirm(selected)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to select organisation')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            key="xero-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-black/70 z-40"
            onClick={loading ? undefined : onClose}
          />
          <motion.div
            key="xero-modal"
            initial={{ opacity: 0, scale: 0.97 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.97 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
          >
            <div className="bg-[#111111] border border-brand-border rounded-sm w-full max-w-md">
              <div className="px-6 py-4 border-b border-brand-border">
                <h2 className="font-heading font-bold text-base text-[#e8f0e8]">
                  Select Xero Organisation
                </h2>
                <p className="text-[10px] font-mono text-brand-muted mt-0.5">
                  Which organisation do you want to connect?
                </p>
              </div>

              <div className="px-6 py-4 space-y-2 max-h-64 overflow-y-auto">
                {orgs.map((org) => (
                  <label
                    key={org.xero_tenant_id}
                    className="flex items-center gap-3 cursor-pointer p-3 rounded-sm border border-brand-border hover:border-[#1e1e1e] transition-colors"
                  >
                    <input
                      type="radio"
                      name="xero-org"
                      value={org.xero_tenant_id}
                      checked={selected === org.xero_tenant_id}
                      onChange={() => setSelected(org.xero_tenant_id)}
                      disabled={loading}
                      className="accent-[#00C853]"
                    />
                    <span className="text-sm font-mono text-[#e8f0e8]">{org.tenantName}</span>
                  </label>
                ))}
                {orgs.length === 0 && (
                  <p className="text-xs font-mono text-brand-muted">No organisations found</p>
                )}
              </div>

              {error && (
                <div className="px-6 pb-2">
                  <p className="text-xs font-mono text-[#ff4d6d] bg-[rgba(255,77,109,0.08)] border border-[rgba(255,77,109,0.2)] rounded-sm px-3 py-2">
                    {error}
                  </p>
                </div>
              )}

              <div className="px-6 py-4 border-t border-brand-border flex gap-3">
                <button
                  onClick={handleConfirm}
                  disabled={loading || !selected}
                  className="flex-1 bg-[#00C853] text-black font-mono text-sm font-medium rounded-sm py-2 hover:bg-[#00a844] active:scale-[0.97] transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {loading ? 'Connecting...' : 'Confirm'}
                </button>
                <button
                  onClick={onClose}
                  disabled={loading}
                  className="flex-1 border border-brand-border text-[#e8f0e8] font-mono text-sm rounded-sm py-2 hover:bg-[#1a1a1a] transition-colors disabled:opacity-40"
                >
                  Cancel
                </button>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
