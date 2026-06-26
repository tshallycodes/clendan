'use client'

import { useEffect, useRef, useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import { motion, AnimatePresence } from 'framer-motion'
import { useToast } from '@/components/Providers'
import { ContractSummaryDrawer } from './ContractSummaryDrawer'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

type DocumentType = 'invoice' | 'receipt' | 'contract'
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
  auto_approved:     { label: 'Auto-approved',     color: 'text-[#00C853]', bg: 'bg-[rgba(0,200,83,0.08)]',   border: 'border-[rgba(0,200,83,0.2)]' },
  approval_required: { label: 'Approval required', color: 'text-[#00a8cc]', bg: 'bg-[rgba(0,168,204,0.08)]', border: 'border-[rgba(0,168,204,0.2)]' },
  blocked:           { label: 'Blocked',            color: 'text-[#ff4d6d]', bg: 'bg-[rgba(255,77,109,0.08)]', border: 'border-[rgba(255,77,109,0.2)]' },
  rejected:          { label: 'Rejected',           color: 'text-[#ff4d6d]', bg: 'bg-[rgba(255,77,109,0.08)]', border: 'border-[rgba(255,77,109,0.2)]' },
}

const DOC_TYPE_LABEL: Record<DocumentType, string> = {
  invoice: 'Invoice',
  receipt: 'Receipt',
  contract: 'Contract',
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function ExtractedFields({ extracted }: { extracted: Record<string, unknown> }) {
  const entries = Object.entries(extracted).filter(
    ([, v]) => v !== null && v !== undefined && v !== '' && !(Array.isArray(v) && v.length === 0)
  )
  if (entries.length === 0) return null
  return (
    <div className="mt-3 space-y-1">
      {entries.map(([key, value]) => (
        <div key={key} className="flex items-start gap-3">
          <span className="text-[10px] font-mono text-brand-muted min-w-[110px] shrink-0">{key}</span>
          <span className="text-[10px] font-mono text-brand-secondary break-all">
            {Array.isArray(value)
              ? value.join(' · ')
              : typeof value === 'object'
                ? JSON.stringify(value)
                : String(value)}
          </span>
        </div>
      ))}
    </div>
  )
}

interface QuickActionsProps {
  doc: ProcessedDocument
  toolId: string
  connectedIntegrations: string[]
  onAbort: (id: string) => void
  onReupload: () => void
  onOpenSummary: (docId: string, filename: string | null) => void
  onUpdateDoc: (docId: string, patch: Partial<ProcessedDocument>) => void
}

function QuickActions({ doc, toolId, connectedIntegrations, onAbort, onReupload, onOpenSummary, onUpdateDoc }: QuickActionsProps) {
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
      a.href = url; a.download = `${doc.filename ?? doc.id}.json`; a.click()
      URL.revokeObjectURL(url)
      toast('Export downloaded', 'success')
    } catch { toast('Network error', 'error') }
    finally { setActionLoading(null) }
  }

  async function handleFlag() {
    setActionLoading('flag')
    try {
      const token = await getToken()
      const res = await fetch(`${API}/v1/documents/${doc.id}/flag`, { method: 'POST', headers: { Authorization: `Bearer ${token}` } })
      if (res.ok) { toast('Flagged for review', 'success') }
      else { const j = await res.json().catch(() => ({})); toast((j as { detail?: string }).detail ?? 'Failed to flag', 'error') }
    } catch { toast('Network error', 'error') }
    finally { setActionLoading(null) }
  }

  async function handlePushAccounting() {
    if (connectedIntegrations.length === 0) return
    setActionLoading('push')
    try {
      const token = await getToken()
      const failed: string[] = []
      for (const integration of connectedIntegrations) {
        const res = await fetch(`${API}/v1/documents/${doc.id}/push-integration`, {
          method: 'POST', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ integration }),
        })
        if (!res.ok) {
          const j = await res.json().catch(() => ({}))
          failed.push((j as { detail?: string }).detail ?? integration)
        }
      }
      if (failed.length === 0) {
        const label = connectedIntegrations.map(i => i.charAt(0).toUpperCase() + i.slice(1)).join(' & ')
        onUpdateDoc(doc.id, { accounting_write_status: `written:${connectedIntegrations[0]}` })
        toast(`Pushed to ${label}`, 'success')
      } else {
        toast(failed.join('; '), 'error')
      }
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
        {doc.decision !== 'approval_required' && (
          <button type="button" onClick={handleFlag} disabled={actionLoading !== null} className={btn}>
            {actionLoading === 'flag' ? '…' : 'Flag for review'}
          </button>
        )}
        {connectedIntegrations.length > 0 && !doc.accounting_write_status?.includes(':') && doc.decision !== 'blocked' && (
          <button
            type="button"
            onClick={doc.decision === 'approval_required' ? () => toast('Approval required before pushing to integration', 'error') : handlePushAccounting}
            disabled={actionLoading !== null}
            className={btn}
          >
            {actionLoading === 'push' ? '…' : `Push to ${connectedIntegrations.map(i => i.charAt(0).toUpperCase() + i.slice(1)).join(' & ')}`}
          </button>
        )}
        <button
          type="button" onClick={handleReupload} disabled={actionLoading !== null}
          className="text-[10px] font-mono px-3 py-1.5 rounded-sm border border-[#ff4d6d] text-[#ff4d6d] bg-[rgba(255,77,109,0.1)] hover:bg-[rgba(255,77,109,0.16)] transition-colors disabled:opacity-50"
        >
          {actionLoading === 'reupload' ? '…' : 'Re-upload'}
        </button>
        {doc.document_type === 'contract' && (
          <button
            type="button" onClick={() => onOpenSummary(doc.id, doc.filename)} disabled={actionLoading !== null}
            className="text-[10px] font-mono px-3 py-1.5 rounded-sm bg-[#00C853] text-black hover:bg-[#00a844] active:scale-[0.97] transition-colors disabled:opacity-50"
          >
            Ask Clen
          </button>
        )}
      </div>
    </div>
  )
}

interface DocumentRowProps {
  doc: ProcessedDocument
  toolId: string
  connectedIntegrations: string[]
  onAbort: (id: string) => void
  onReupload: () => void
  onOpenSummary: (docId: string, filename: string | null) => void
  onUpdateDoc: (docId: string, patch: Partial<ProcessedDocument>) => void
}

function DocumentRow({ doc, toolId, connectedIntegrations, onAbort, onReupload, onOpenSummary, onUpdateDoc }: DocumentRowProps) {
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
            <img
              src={`data:image/png;base64,${doc.thumbnail_b64}`}
              alt="doc"
              className="w-full h-full object-cover"
            />
          ) : (
            <span className="text-[10px] font-mono text-brand-muted">PDF</span>
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
                  {DOC_TYPE_LABEL[doc.document_type]}
                </span>
                {doc.file_size_bytes != null && (
                  <span className="text-[10px] font-mono text-brand-muted">{formatBytes(doc.file_size_bytes)}</span>
                )}
                {uploader && (
                  <span className="text-[10px] font-mono text-brand-muted">{uploader}</span>
                )}
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
              {doc.status === 'completed' && doc.decision === 'blocked' && (
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
            <div className="px-4 pb-4 border-t border-brand-border space-y-3">
              {/* Extracted fields */}
              {doc.extracted_json && Object.keys(doc.extracted_json).length > 0 && (
                <div>
                  <p className="text-[10px] font-mono text-brand-muted uppercase tracking-widest mt-3 mb-1.5">
                    Extracted fields
                  </p>
                  <ExtractedFields extracted={doc.extracted_json} />
                </div>
              )}

              {/* Policy flags */}
              {doc.flags_json && doc.flags_json.length > 0 && (
                <div>
                  <p className="text-[10px] font-mono text-brand-muted uppercase tracking-widest mb-1.5">Policy flags</p>
                  <div className="space-y-1">
                    {doc.flags_json.map((flag, i) => (
                      <div key={i} className="bg-[rgba(245,166,35,0.04)] border border-[rgba(245,166,35,0.2)] rounded-sm px-3 py-2">
                        <p className="text-[11px] font-mono text-brand-secondary">{flag}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Accounting write status */}
              {doc.accounting_write_status && doc.accounting_write_status !== 'skipped' && (() => {
                const hasIntegration = doc.accounting_write_status.includes(':')
                const integration = hasIntegration ? doc.accounting_write_status.split(':')[1] : null
                const isFailed = doc.accounting_write_status === 'failed'
                const label = hasIntegration
                  ? `Pushed to ${integration!.charAt(0).toUpperCase() + integration!.slice(1)} — already synced, re-push blocked`
                  : isFailed
                    ? 'Write failed'
                    : 'Not synced — select an integration below to push'
                return (
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono text-brand-muted uppercase tracking-widest">Accounting write</span>
                    <span className={`text-[10px] font-mono ${
                      hasIntegration ? 'text-[#00C853]' :
                      isFailed ? 'text-[#ff4d6d]' : 'text-[#f5a623]'
                    }`}>
                      {label}
                    </span>
                  </div>
                )
              })()}

              {/* Quick actions — completed documents only */}
              {doc.status === 'completed' && (
                <QuickActions
                  doc={doc}
                  toolId={toolId}
                  connectedIntegrations={connectedIntegrations}
                  onAbort={onAbort}
                  onReupload={onReupload}
                  onOpenSummary={onOpenSummary}
                  onUpdateDoc={onUpdateDoc}
                />
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function UploadArea({
  docType,
  setDocType,
  uploading,
  onFiles,
}: {
  docType: DocumentType
  setDocType: (t: DocumentType) => void
  uploading: boolean
  onFiles: (files: FileList) => void
}) {
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-[10px] font-mono text-brand-muted uppercase tracking-widest">Document type</span>
        {(['invoice', 'receipt', 'contract'] as DocumentType[]).map(t => (
          <button
            key={t}
            type="button"
            onClick={() => setDocType(t)}
            className={`text-[10px] font-mono px-2.5 py-1 rounded-sm border transition-colors ${
              docType === t
                ? 'border-[#00C853] text-[#00C853] bg-[rgba(0,200,83,0.08)]'
                : 'border-brand-border text-brand-muted hover:text-brand-secondary'
            }`}
          >
            {DOC_TYPE_LABEL[t]}
          </button>
        ))}
      </div>

      <div
        onDragOver={e => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={e => { e.preventDefault(); setDragOver(false); if (e.dataTransfer.files.length) onFiles(e.dataTransfer.files) }}
        onClick={() => inputRef.current?.click()}
        className={`relative border-2 border-dashed rounded-sm p-8 text-center cursor-pointer transition-colors ${
          dragOver
            ? 'border-[#00C853] bg-[rgba(0,200,83,0.04)]'
            : 'border-brand-border hover:border-brand-secondary'
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.png,.jpg,.jpeg,.webp"
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
              Drop a {DOC_TYPE_LABEL[docType].toLowerCase()} here or click to browse
            </p>
            <p className="text-[10px] font-mono text-brand-muted">PDF · PNG · JPG · WebP · max 10 MB</p>
          </div>
        )}
      </div>
    </div>
  )
}

export function DocumentsTab({ toolId, connectedIntegrations = [] }: { toolId: string | null; connectedIntegrations?: string[] }) {
  const { getToken } = useAuth()
  const { toast } = useToast()
  const [documents, setDocuments] = useState<ProcessedDocument[]>([])
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [docType, setDocType] = useState<DocumentType>('invoice')
  const [summaryDocId, setSummaryDocId] = useState<string | null>(null)
  const [summaryFilename, setSummaryFilename] = useState<string | null>(null)
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

  // Poll every 3 s while any real (non-temp) document is still processing
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
        setDocuments(prev => prev.map(d => {
          if (d.id.startsWith('temp-')) return d
          const updated = fresh.find(f => f.id === d.id)
          return updated ?? d
        }))
        setTotal(json.data.total)
      } catch {
        // polling failure is non-fatal
      }
    }, 3000)
    return () => clearInterval(id)
  }, [hasProcessing, toolId, getToken])

  async function handleFiles(files: FileList) {
    if (!toolId) return
    const file = files[0]
    const tempId = `temp-${Date.now()}`
    const now = new Date().toISOString()

    // Add placeholder immediately — state update in this component, no callback chain
    setDocuments(prev => [{
      id: tempId,
      document_type: docType,
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
        `${API}/v1/document-intelligence/${toolId}/upload?document_type=${docType}`,
        { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: form },
      )
      const json = await res.json()
      if (!res.ok) {
        toast(json.detail ?? 'Upload failed', 'error')
        setDocuments(prev => prev.filter(d => d.id !== tempId))
        setTotal(t => t - 1)
        return
      }
      toast('Document uploaded — processing started', 'success')
      setDocuments(prev => prev.map(d => d.id === tempId ? {
        id: json.data.document_id,
        document_type: docType,
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

  function handleAborted(docId: string) {
    setDocuments(prev => prev.filter(d => d.id !== docId))
    setTotal(t => t - 1)
  }

  function handleUpdateDoc(docId: string, patch: Partial<ProcessedDocument>) {
    setDocuments(prev => prev.map(d => d.id === docId ? { ...d, ...patch } : d))
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
        <UploadArea docType={docType} setDocType={setDocType} uploading={uploading} onFiles={handleFiles} />
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
                  connectedIntegrations={connectedIntegrations}
                  onAbort={handleAborted}
                  onReupload={() => uploadRef.current?.scrollIntoView({ behavior: 'smooth' })}
                  onOpenSummary={(id, filename) => { setSummaryDocId(id); setSummaryFilename(filename) }}
                  onUpdateDoc={handleUpdateDoc}
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

      {summaryDocId !== null && (
        <ContractSummaryDrawer
          documentId={summaryDocId}
          filename={summaryFilename}
          onClose={() => { setSummaryDocId(null); setSummaryFilename(null) }}
        />
      )}
    </div>
  )
}
