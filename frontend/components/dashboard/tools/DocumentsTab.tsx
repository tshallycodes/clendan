'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import { motion, AnimatePresence } from 'framer-motion'
import { useToast } from '@/components/Providers'

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

function DocumentRow({ doc, toolId, onAbort }: { doc: ProcessedDocument; toolId: string; onAbort: (id: string) => void }) {
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
                  <span className="text-[10px] font-mono text-[#f5a623] bg-[rgba(245,166,35,0.08)] border border-[rgba(245,166,35,0.2)] rounded-sm px-2 py-0.5">
                    Processing…
                  </span>
                  <button
                    type="button"
                    onClick={e => handleDelete(e, 'Aborted')}
                    disabled={aborting}
                    className="text-[10px] font-mono text-[#ff4d6d] bg-[rgba(255,77,109,0.06)] border border-[rgba(255,77,109,0.3)] hover:bg-[rgba(255,77,109,0.12)] rounded-sm px-2 py-0.5 transition-colors disabled:opacity-50"
                  >
                    {aborting ? 'Aborting…' : 'Abort'}
                  </button>
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
              {doc.accounting_write_status && doc.accounting_write_status !== 'skipped' && (
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono text-brand-muted uppercase tracking-widest">Accounting write</span>
                  <span className={`text-[10px] font-mono ${
                    doc.accounting_write_status === 'written' ? 'text-[#00C853]' :
                    doc.accounting_write_status === 'failed' ? 'text-[#ff4d6d]' : 'text-brand-muted'
                  }`}>
                    {doc.accounting_write_status}
                  </span>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function UploadArea({
  toolId,
  onUploaded,
}: {
  toolId: string
  onUploaded: (doc: ProcessedDocument) => void
}) {
  const { getToken } = useAuth()
  const { toast } = useToast()
  const [dragOver, setDragOver] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [docType, setDocType] = useState<DocumentType>('invoice')
  const inputRef = useRef<HTMLInputElement>(null)

  async function uploadFile(file: File) {
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
        return
      }
      toast('Document uploaded — processing started', 'success')
      onUploaded({
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
        created_at: new Date().toISOString(),
      })
    } catch {
      toast('Network error — please try again', 'error')
    } finally {
      setUploading(false)
    }
  }

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files || files.length === 0) return
      uploadFile(files[0])
    },
    [docType, toolId],
  )

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
        onDrop={e => { e.preventDefault(); setDragOver(false); handleFiles(e.dataTransfer.files) }}
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
          onChange={e => handleFiles(e.target.files)}
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

export function DocumentsTab({ toolId }: { toolId: string | null }) {
  const { getToken } = useAuth()
  const [documents, setDocuments] = useState<ProcessedDocument[]>([])
  const [loading, setLoading] = useState(false)
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
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

  function handleUploaded(doc: ProcessedDocument) {
    setDocuments(prev => [doc, ...prev])
    setTotal(t => t + 1)
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
      <UploadArea toolId={toolId} onUploaded={handleUploaded} />

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
                <DocumentRow key={doc.id} doc={doc} toolId={toolId} onAbort={handleAborted} />
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
