'use client'

import { useEffect, useRef, useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import { motion, AnimatePresence } from 'framer-motion'
import { useToast } from '@/components/Providers'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

type DocumentType = 'receipt' | 'document' | 'pending'
type DocumentStatus = 'processing' | 'completed' | 'failed'

interface ProcessedDocument {
  id: string
  document_type: DocumentType
  filename: string | null
  content_type: string
  file_size_bytes: number | null
  uploaded_by: string | null
  status: DocumentStatus
  decision: string | null
  confidence: number | null
  rule_triggered: string | null
  reason: string | null
  flags_json: string[] | null
  extracted_json: Record<string, unknown> | null
  thumbnail_b64: string | null
  accounting_write_status: string | null
  created_at: string
}

const DECISION_CONFIG: Record<string, { label: string; color: string; bg: string; border: string }> = {
  auto_pushed:           { label: 'Pushed',              color: 'text-[#00C853]',  bg: 'bg-[rgba(0,200,83,0.08)]',   border: 'border-[rgba(0,200,83,0.2)]' },
  analysed:              { label: 'Analysed',            color: 'text-[#00C853]',  bg: 'bg-[rgba(0,200,83,0.08)]',   border: 'border-[rgba(0,200,83,0.2)]' },
  push_failed:           { label: 'Push failed',         color: 'text-[#ff4d6d]',  bg: 'bg-[rgba(255,77,109,0.08)]', border: 'border-[rgba(255,77,109,0.2)]' },
  classification_failed: { label: 'Could not classify',  color: 'text-[#ff4d6d]',  bg: 'bg-[rgba(255,77,109,0.08)]', border: 'border-[rgba(255,77,109,0.2)]' },
  blocked:               { label: 'Blocked',             color: 'text-[#ff4d6d]',  bg: 'bg-[rgba(255,77,109,0.08)]', border: 'border-[rgba(255,77,109,0.2)]' },
  auto_approved:         { label: 'Auto-approved',       color: 'text-[#00C853]',  bg: 'bg-[rgba(0,200,83,0.08)]',   border: 'border-[rgba(0,200,83,0.2)]' },
  approval_required:     { label: 'Needs review',        color: 'text-[#00a8cc]',  bg: 'bg-[rgba(0,168,204,0.08)]',  border: 'border-[rgba(0,168,204,0.2)]' },
}

const DOC_TYPE_LABEL: Record<string, string> = {
  receipt:  'Receipt',
  document: 'Document',
  pending:  'Classifying…',
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatCurrency(amount_minor: number, currency: string): string {
  const symbols: Record<string, string> = { GBP: '£', USD: '$', EUR: '€' }
  const symbol = symbols[currency?.toUpperCase()] ?? currency ?? ''
  return `${symbol}${(amount_minor / 100).toFixed(2)}`
}

function ReceiptFields({ extracted }: { extracted: Record<string, unknown> }) {
  const amount_minor = extracted.amount_minor as number | undefined
  const currency = extracted.currency as string | undefined
  const merchant = extracted.merchant as string | undefined
  const date = extracted.date as string | undefined
  const category = extracted.category as string | undefined

  const fields = [
    { label: 'Merchant', value: merchant },
    { label: 'Amount',   value: amount_minor != null && currency ? formatCurrency(amount_minor, currency) : undefined },
    { label: 'Date',     value: date },
    { label: 'Category', value: category?.replace(/_/g, ' ') },
  ].filter(f => f.value)

  return (
    <div className="grid grid-cols-2 gap-x-6 gap-y-2 mt-1">
      {fields.map(({ label, value }) => (
        <div key={label}>
          <p className="text-[10px] font-mono text-brand-muted">{label}</p>
          <p className="text-xs font-mono text-brand-text">{value}</p>
        </div>
      ))}
    </div>
  )
}

function AccordionSection({ title, items, color = 'text-brand-secondary' }: { title: string; items: string[]; color?: string }) {
  const [open, setOpen] = useState(false)
  if (!items?.length) return null
  return (
    <div className="border border-brand-border rounded-sm overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center justify-between px-3 py-2 hover:bg-brand-elevated transition-colors text-left"
      >
        <span className="text-[10px] font-mono text-brand-muted uppercase tracking-widest">
          {title} <span className="text-brand-secondary normal-case tracking-normal">({items.length})</span>
        </span>
        <span className="text-[10px] font-mono text-brand-muted">{open ? '▲' : '▼'}</span>
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0 }}
            animate={{ height: 'auto' }}
            exit={{ height: 0 }}
            transition={{ duration: 0.15 }}
            className="overflow-hidden"
          >
            <div className="border-t border-brand-border divide-y divide-brand-border-subtle">
              {items.map((item, i) => (
                <div key={i} className="flex gap-2 px-3 py-2">
                  <span className="text-[10px] font-mono text-brand-muted shrink-0 mt-0.5">→</span>
                  <p className={`text-[11px] font-mono leading-relaxed ${color}`}>{item}</p>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function DocumentAnalysis({ extracted }: { extracted: Record<string, unknown> }) {
  const summary = extracted.summary as string | undefined
  const risks = extracted.risks as string[] | undefined
  const loopholes = extracted.loopholes as string[] | undefined
  const improvements = extracted.improvements as string[] | undefined
  const parties = extracted.parties as string[] | undefined
  const keyDates = extracted.key_dates as string[] | undefined

  return (
    <div className="space-y-3 mt-1">
      {summary && (
        <div>
          <p className="text-[10px] font-mono text-brand-muted uppercase tracking-widest mb-1.5">Summary</p>
          <p className="text-xs font-mono text-brand-secondary leading-relaxed">{summary}</p>
        </div>
      )}
      {(parties?.length || keyDates?.length) ? (
        <div className="grid grid-cols-2 gap-x-6 gap-y-2">
          {parties?.length ? (
            <div>
              <p className="text-[10px] font-mono text-brand-muted mb-1">Parties</p>
              <div className="space-y-0.5">
                {parties.map((p, i) => <p key={i} className="text-[11px] font-mono text-brand-secondary">{p}</p>)}
              </div>
            </div>
          ) : null}
          {keyDates?.length ? (
            <div>
              <p className="text-[10px] font-mono text-brand-muted mb-1">Key dates</p>
              <div className="space-y-0.5">
                {keyDates.map((d, i) => <p key={i} className="text-[11px] font-mono text-brand-secondary">{d}</p>)}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
      <AccordionSection title="Risks" items={risks ?? []} color="text-[#ff4d6d]" />
      <AccordionSection title="Loopholes" items={loopholes ?? []} color="text-[#f5a623]" />
      <AccordionSection title="Improvements" items={improvements ?? []} />
    </div>
  )
}

interface QuickActionsProps {
  doc: ProcessedDocument
  toolId: string
  onAbort: (id: string) => void
  onReupload: () => void
}

function QuickActions({ doc, toolId, onAbort, onReupload }: QuickActionsProps) {
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const { getToken } = useAuth()
  const { toast } = useToast()

  async function handleExport() {
    setActionLoading('export')
    try {
      const token = await getToken()
      const res = await fetch(`${API}/v1/documents/${doc.id}/export`, { headers: { Authorization: `Bearer ${token}` } })
      if (!res.ok) { toast('Export failed', 'error'); return }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      const raw = doc.filename ?? doc.id
      const base = raw.includes('.') ? raw.substring(0, raw.lastIndexOf('.')) : raw
      a.download = `${base}.json`
      a.click()
      URL.revokeObjectURL(url)
      toast('Export downloaded', 'success')
    } catch { toast('Network error', 'error') }
    finally { setActionLoading(null) }
  }

  async function handleReupload() {
    setActionLoading('reupload')
    try {
      const token = await getToken()
      const res = await fetch(`${API}/v1/document-intelligence/${toolId}/documents/${doc.id}/abort`, { method: 'POST', headers: { Authorization: `Bearer ${token}` } })
      if (res.ok) { toast('Document removed — re-upload to reprocess', 'success'); onAbort(doc.id); onReupload() }
      else { const j = await res.json().catch(() => ({})); toast((j as { detail?: string }).detail ?? 'Failed', 'error') }
    } catch { toast('Network error', 'error') }
    finally { setActionLoading(null) }
  }

  const btn = 'text-[10px] font-mono px-3 py-1.5 rounded-sm border border-brand-border text-brand-text bg-transparent hover:bg-brand-elevated transition-colors disabled:opacity-50'

  return (
    <div className="pt-3 border-t border-brand-border">
      <p className="text-[10px] font-mono text-brand-muted uppercase tracking-widest mb-2">Quick actions</p>
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={handleExport} disabled={actionLoading !== null} className={btn}>
          {actionLoading === 'export' ? '…' : 'Export JSON'}
        </button>
        <button
          type="button"
          onClick={handleReupload}
          disabled={actionLoading !== null}
          className="text-[10px] font-mono px-3 py-1.5 rounded-sm border border-[#ff4d6d] text-[#ff4d6d] bg-[rgba(255,77,109,0.1)] hover:bg-[rgba(255,77,109,0.16)] transition-colors disabled:opacity-50"
        >
          {actionLoading === 'reupload' ? '…' : 'Re-upload'}
        </button>
      </div>
    </div>
  )
}

interface DocumentRowProps {
  doc: ProcessedDocument
  toolId: string
  onAbort: (id: string) => void
  onReupload: () => void
}

function DocumentRow({ doc, toolId, onAbort, onReupload }: DocumentRowProps) {
  const [expanded, setExpanded] = useState(false)
  const [aborting, setAborting] = useState(false)
  const { getToken } = useAuth()
  const { toast } = useToast()
  const dc = doc.decision ? (DECISION_CONFIG[doc.decision] ?? null) : null

  async function handleDelete(e: React.MouseEvent, label: string) {
    e.stopPropagation()
    setAborting(true)
    try {
      const token = await getToken()
      const res = await fetch(
        `${API}/v1/document-intelligence/${toolId}/documents/${doc.id}/abort`,
        { method: 'POST', headers: { Authorization: `Bearer ${token}` } },
      )
      if (res.ok) {
        toast(`Document ${label.toLowerCase()}`, 'success')
        onAbort(doc.id)
      } else {
        const json = await res.json().catch(() => ({}))
        toast((json as { detail?: string }).detail ?? 'Failed', 'error')
      }
    } catch {
      toast('Network error', 'error')
    } finally {
      setAborting(false)
    }
  }

  const uploader = doc.uploaded_by ? doc.uploaded_by.split('@')[0] : null
  const date = new Date(doc.created_at).toLocaleString('en-GB', {
    day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
  })
  const timedOut = doc.status === 'processing' && !doc.id.startsWith('temp-') &&
    Date.now() - new Date(doc.created_at).getTime() > 10 * 60 * 1000

  const showAnalysis = doc.status === 'completed' && doc.extracted_json && Object.keys(doc.extracted_json).length > 0
  const accountingStatus = doc.accounting_write_status

  return (
    <div className="border-b border-brand-border last:border-0">
      <button
        type="button"
        onClick={() => setExpanded(v => !v)}
        className="w-full flex items-stretch gap-4 p-4 hover:bg-brand-elevated transition-colors text-left"
      >
        {/* Thumbnail */}
        <div className="shrink-0 w-[52px] h-[72px] bg-brand-bg border border-brand-border rounded-sm overflow-hidden flex items-center justify-center">
          {doc.thumbnail_b64 ? (
            <img src={`data:image/png;base64,${doc.thumbnail_b64}`} alt="doc" className="w-full h-full object-cover" />
          ) : (
            <span className="text-[10px] font-mono text-brand-muted">
              {doc.content_type?.includes('word') ? 'DOC' : 'PDF'}
            </span>
          )}
        </div>

        {/* Main content */}
        <div className="flex-1 min-w-0 space-y-1.5">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs font-mono text-brand-text truncate">
                {doc.filename ?? 'Untitled document'}
              </p>
              <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                <span className="text-[10px] font-mono text-brand-muted uppercase tracking-widest">
                  {DOC_TYPE_LABEL[doc.document_type] ?? doc.document_type}
                </span>
                {doc.file_size_bytes != null && (
                  <span className="text-[10px] font-mono text-brand-muted">{formatBytes(doc.file_size_bytes)}</span>
                )}
                {uploader && <span className="text-[10px] font-mono text-brand-muted">{uploader}</span>}
                <span className="text-[10px] font-mono text-brand-muted">{date}</span>
              </div>
            </div>
            <div className="shrink-0 flex items-center gap-2">
              {doc.status === 'processing' && (
                <>
                  <span className={`text-[10px] font-mono px-2 py-0.5 rounded-sm border ${
                    timedOut
                      ? 'text-[#ff4d6d] bg-[rgba(255,77,109,0.08)] border-[rgba(255,77,109,0.2)]'
                      : 'text-[#f5a623] bg-[rgba(245,166,35,0.08)] border-[rgba(245,166,35,0.2)]'
                  }`}>
                    {doc.id.startsWith('temp-') ? 'Uploading…' : timedOut ? 'Timed out' : 'Processing…'}
                  </span>
                  {!doc.id.startsWith('temp-') && (
                    <button
                      type="button"
                      onClick={e => handleDelete(e, timedOut ? 'Deleted' : 'Aborted')}
                      disabled={aborting}
                      className="text-[10px] font-mono text-[#ff4d6d] bg-[rgba(255,77,109,0.06)] border border-[rgba(255,77,109,0.3)] hover:bg-[rgba(255,77,109,0.12)] rounded-sm px-2 py-0.5 transition-colors disabled:opacity-50"
                    >
                      {aborting ? 'Deleting…' : timedOut ? 'Delete' : 'Abort'}
                    </button>
                  )}
                </>
              )}
              {doc.status === 'failed' && (
                <>
                  <span className="text-[10px] font-mono text-[#ff4d6d] bg-[rgba(255,77,109,0.08)] border border-[rgba(255,77,109,0.2)] rounded-sm px-2 py-0.5">
                    Failed
                  </span>
                  <button
                    type="button"
                    onClick={e => handleDelete(e, 'Deleted')}
                    disabled={aborting}
                    className="text-[10px] font-mono text-[#ff4d6d] bg-[rgba(255,77,109,0.06)] border border-[rgba(255,77,109,0.3)] hover:bg-[rgba(255,77,109,0.12)] rounded-sm px-2 py-0.5 transition-colors disabled:opacity-50"
                  >
                    {aborting ? 'Deleting…' : 'Delete'}
                  </button>
                </>
              )}
              {doc.status === 'completed' && (dc?.color === 'text-[#ff4d6d]') && (
                <button
                  type="button"
                  onClick={e => handleDelete(e, 'Deleted')}
                  disabled={aborting}
                  className="text-[10px] font-mono text-[#ff4d6d] bg-[rgba(255,77,109,0.06)] border border-[rgba(255,77,109,0.3)] hover:bg-[rgba(255,77,109,0.12)] rounded-sm px-2 py-0.5 transition-colors disabled:opacity-50"
                >
                  {aborting ? 'Deleting…' : 'Delete'}
                </button>
              )}
              {dc && (
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded-sm border ${dc.bg} ${dc.border} ${dc.color}`}>
                  {dc.label}
                </span>
              )}
              {doc.confidence != null && (
                <span className={`text-[10px] font-mono ${doc.confidence >= 0.9 ? 'text-[#00C853]' : 'text-brand-muted'}`}>
                  {Math.round(doc.confidence * 100)}%
                </span>
              )}
              <span className="text-[10px] font-mono text-brand-muted">{expanded ? '▲' : '▼'}</span>
            </div>
          </div>

          {doc.reason && (
            <p className="text-[10px] font-mono text-brand-muted truncate">{doc.reason}</p>
          )}
        </div>
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.18, ease: 'easeOut' }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 border-t border-brand-border space-y-4">
              {showAnalysis && (
                <div className="mt-3">
                  {doc.document_type === 'receipt' && (
                    <>
                      <p className="text-[10px] font-mono text-brand-muted uppercase tracking-widest mb-2">Receipt details</p>
                      <ReceiptFields extracted={doc.extracted_json!} />
                    </>
                  )}
                  {doc.document_type === 'document' && (
                    <>
                      <p className="text-[10px] font-mono text-brand-muted uppercase tracking-widest mb-2">
                        Analysis
                        {!!doc.extracted_json?.document_subtype && (
                          <span className="ml-2 normal-case tracking-normal text-brand-secondary">
                            — {String(doc.extracted_json.document_subtype).replace(/_/g, ' ')}
                          </span>
                        )}
                      </p>
                      <DocumentAnalysis extracted={doc.extracted_json!} />
                    </>
                  )}
                </div>
              )}

              {/* Accounting write status (receipts) */}
              {accountingStatus && (() => {
                const parts = accountingStatus.split(',').filter(p => p.includes(':'))
                const written = parts.filter(p => p.startsWith('written:')).map(p => p.split(':')[1])
                const failed = parts.filter(p => p.startsWith('failed:')).map(p => p.split(':')[1])
                if (!written.length && !failed.length) return null
                return (
                  <div className="space-y-1">
                    {written.length > 0 && (
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-mono text-brand-muted uppercase tracking-widest">Pushed to</span>
                        <span className="text-[10px] font-mono text-[#00C853]">
                          {written.map(i => i.charAt(0).toUpperCase() + i.slice(1)).join(', ')}
                        </span>
                      </div>
                    )}
                    {failed.length > 0 && (
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-mono text-brand-muted uppercase tracking-widest">Push failed</span>
                        <span className="text-[10px] font-mono text-[#ff4d6d]">
                          {failed.map(i => i.charAt(0).toUpperCase() + i.slice(1)).join(', ')}
                        </span>
                      </div>
                    )}
                  </div>
                )
              })()}

              {doc.status === 'completed' && (
                <QuickActions
                  doc={doc}
                  toolId={toolId}
                  onAbort={onAbort}
                  onReupload={onReupload}
                />
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function UploadArea({ uploading, onFiles }: { uploading: boolean; onFiles: (files: FileList) => void }) {
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  return (
    <div
      onDragOver={e => { e.preventDefault(); setDragOver(true) }}
      onDragLeave={() => setDragOver(false)}
      onDrop={e => { e.preventDefault(); setDragOver(false); if (e.dataTransfer.files.length) onFiles(e.dataTransfer.files) }}
      onClick={() => inputRef.current?.click()}
      className={`relative border-2 border-dashed rounded-sm p-8 text-center cursor-pointer transition-colors ${
        dragOver ? 'border-[#00C853] bg-[rgba(0,200,83,0.04)]' : 'border-brand-border hover:border-brand-secondary'
      }`}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.doc,.docx,.png,.jpg,.jpeg,.webp"
        multiple
        className="sr-only"
        onChange={e => { if (e.target.files?.length) onFiles(e.target.files) }}
      />
      {uploading ? (
        <div className="space-y-1.5">
          <div className="w-5 h-5 border-2 border-[#00C853] border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-xs font-mono text-brand-muted">Uploading…</p>
        </div>
      ) : (
        <div className="space-y-1.5">
          <p className="text-xs font-mono text-brand-secondary">
            Drop files here or click to browse
          </p>
          <p className="text-[10px] font-mono text-brand-muted">
            PDF · Word · PNG · JPG · WebP · max 10 MB
          </p>
          <p className="text-[10px] font-mono text-brand-muted mt-1">
            Clen auto-classifies as receipt or document
          </p>
        </div>
      )}
    </div>
  )
}

export function DocumentsTab({ toolId }: { toolId: string | null }) {
  const { getToken } = useAuth()
  const { toast } = useToast()
  const [documents, setDocuments] = useState<ProcessedDocument[]>([])
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const uploadRef = useRef<HTMLDivElement>(null)
  const limit = 20

  async function load(off = 0) {
    if (!toolId) return
    setLoading(true)
    try {
      const token = await getToken()
      const res = await fetch(
        `${API}/v1/document-intelligence/${toolId}/documents?limit=${limit}&offset=${off}`,
        { headers: { Authorization: `Bearer ${token}` } },
      )
      if (res.ok) {
        const json = await res.json()
        setDocuments(off === 0 ? json.data.documents : prev => [...prev, ...json.data.documents])
        setTotal(json.data.total)
        setOffset(off)
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load(0) }, [toolId])

  const hasProcessing = documents.some(d => d.status === 'processing' && !d.id.startsWith('temp-'))
  useEffect(() => {
    if (!hasProcessing || !toolId) return
    const id = setInterval(async () => {
      try {
        const token = await getToken()
        const res = await fetch(
          `${API}/v1/document-intelligence/${toolId}/documents?limit=${limit}&offset=0`,
          { headers: { Authorization: `Bearer ${token}` } },
        )
        if (!res.ok) return
        const json = await res.json()
        const fresh: ProcessedDocument[] = json.data.documents
        setDocuments(prev => {
          const next = prev.map(d => {
            if (d.id.startsWith('temp-')) return d
            const updated = fresh.find(f => f.id === d.id)
            if (updated && d.status === 'processing' && updated.status === 'completed') {
              const isSuccess = ['auto_pushed', 'analysed', 'auto_approved'].includes(updated.decision ?? '')
              const label = DECISION_CONFIG[updated.decision ?? '']?.label ?? 'Processed'
              const name = updated.filename ?? 'Document'
              setTimeout(() => toast(`${name}: ${label}`, isSuccess ? 'success' : 'error'), 0)
            }
            return updated ?? d
          })
          return next
        })
        setTotal(json.data.total)
      } catch {
        // polling failure is non-fatal
      }
    }, 3000)
    return () => clearInterval(id)
  }, [hasProcessing, toolId, getToken])

  async function handleFiles(files: FileList) {
    if (!toolId) return

    for (let i = 0; i < files.length; i++) {
      const file = files[i]
      const tempId = `temp-${Date.now()}-${i}`
      const now = new Date().toISOString()

      setDocuments(prev => [{
        id: tempId,
        document_type: 'pending',
        filename: file.name,
        content_type: file.type,
        file_size_bytes: file.size,
        uploaded_by: null,
        status: 'processing',
        decision: null,
        confidence: null,
        rule_triggered: null,
        reason: null,
        flags_json: null,
        extracted_json: null,
        thumbnail_b64: null,
        accounting_write_status: null,
        created_at: now,
      }, ...prev])
      setTotal(t => t + 1)
      setUploading(true)

      try {
        const token = await getToken()
        const form = new FormData()
        form.append('file', file)
        const res = await fetch(
          `${API}/v1/document-intelligence/${toolId}/upload`,
          { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: form },
        )
        const json = await res.json()
        if (!res.ok) {
          toast(json.detail ?? 'Upload failed', 'error')
          setDocuments(prev => prev.filter(d => d.id !== tempId))
          setTotal(t => t - 1)
          continue
        }
        toast(`${file.name} uploaded — classifying…`, 'success')
        setDocuments(prev => prev.map(d => d.id === tempId ? {
          id: json.data.document_id,
          document_type: 'pending' as DocumentType,
          filename: file.name,
          content_type: file.type,
          file_size_bytes: file.size,
          uploaded_by: null,
          status: 'processing' as DocumentStatus,
          decision: null,
          confidence: null,
          rule_triggered: null,
          reason: null,
          flags_json: null,
          extracted_json: null,
          thumbnail_b64: json.data.thumbnail_b64 ?? null,
          accounting_write_status: null,
          created_at: now,
        } : d))
      } catch {
        toast('Network error — please try again', 'error')
        setDocuments(prev => prev.filter(d => d.id !== tempId))
        setTotal(t => t - 1)
      } finally {
        setUploading(false)
      }
    }
  }

  function handleAborted(docId: string) {
    setDocuments(prev => prev.filter(d => d.id !== docId))
    setTotal(t => t - 1)
  }

  if (!toolId) {
    return (
      <div className="bg-brand-surface border border-brand-border rounded-sm p-8 text-center">
        <p className="text-xs font-mono text-brand-muted">Deploy the tool to start uploading documents.</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div ref={uploadRef}>
        <UploadArea uploading={uploading} onFiles={handleFiles} />
      </div>

      <div>
        <div className="flex items-center justify-between mb-2">
          <p className="text-[10px] font-mono text-brand-muted uppercase tracking-widest">
            Documents · {total}
          </p>
          <button
            type="button"
            onClick={() => load(0)}
            className="text-[10px] font-mono text-brand-muted hover:text-brand-secondary transition-colors"
          >
            Refresh
          </button>
        </div>

        {loading && documents.length === 0 ? (
          <div className="bg-brand-surface border border-brand-border rounded-sm p-8 text-center">
            <p className="text-xs font-mono text-brand-muted">Loading…</p>
          </div>
        ) : documents.length === 0 ? (
          <div className="bg-brand-surface border border-brand-border rounded-sm p-8 text-center">
            <p className="text-xs font-mono text-brand-muted">No documents yet — upload one above.</p>
          </div>
        ) : (
          <>
            <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
              {documents.map(doc => (
                <DocumentRow
                  key={doc.id}
                  doc={doc}
                  toolId={toolId}
                  onAbort={handleAborted}
                  onReupload={() => uploadRef.current?.scrollIntoView({ behavior: 'smooth' })}
                />
              ))}
            </div>

            {documents.length < total && (
              <button
                type="button"
                onClick={() => load(offset + limit)}
                disabled={loading}
                className="w-full mt-2 text-xs font-mono text-brand-muted border border-brand-border rounded-sm py-2 hover:bg-brand-elevated transition-colors disabled:opacity-50"
              >
                {loading ? 'Loading…' : `Load more (${total - documents.length} remaining)`}
              </button>
            )}
          </>
        )}
      </div>

    </div>
  )
}
