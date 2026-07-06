export const TEST_PAYLOADS: Record<string, { event_type: string; payload: Record<string, unknown> }> = {
  reconciliation:      { event_type: 'reconciliation_run',         payload: { period_days: 30 } },
  document_intelligence: { event_type: 'document_received',        payload: { document_type: 'invoice' } },
  spend_control:       { event_type: 'spend_control_run',          payload: { transaction_ids: [] } },
  tax_compliance:      { event_type: 'tax_compliance_run',         payload: {} },
  financial_reporting: { event_type: 'financial_report_run',       payload: {} },
  payment_run:         { event_type: 'payment_run_requested',      payload: {} },
}
