export interface ReconciliationRun {
  id: string
  period_start: string
  period_end: string
  status: string
  matched_count: number
  unmatched_count: number
  flagged_count: number
  review_count: number
  total_txn_count: number
  triggered_by_email: string | null
  created_at: string
}

export interface ReconciliationItem {
  id: string
  date: string
  account_name: string | null
  account_id: string
  description: string
  merchant_name: string | null
  amount_minor: number
  currency: string
  status: string
  ai_action: 'flag' | 'review' | 'ok' | null
  ai_severity: 'high' | 'medium' | 'low' | null
  matched_invoice_number: string | null
  matched_vendor: string | null
  matched_source: string | null
  reasoning: string
}
