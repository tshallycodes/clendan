export const TEST_PAYLOADS: Record<string, { event_type: string; payload: Record<string, unknown> }> = {
  fraud_detection:     { event_type: 'fraud_check_requested',     payload: { transaction_ids: [] } },
  collections:         { event_type: 'collection_triggered',      payload: {} },
  revenue_recognition: { event_type: 'revenue_recognition_run',   payload: { contract_type: 'subscription', amount_minor: 120000, currency: 'GBP' } },
  credit_underwriting: { event_type: 'credit_underwriting_run',   payload: { applicant_id: 'test-001', requested_amount_minor: 500000 } },
  compliance:          { event_type: 'compliance_check_requested', payload: { transaction_ids: [], frameworks: ['AML', 'KYC'] } },
  reconciliation:      { event_type: 'reconciliation_run',        payload: { period_days: 30 } },
  expense_control:     { event_type: 'expense_control_run',       payload: { transaction_ids: [] } },
  treasury:            { event_type: 'treasury_run',              payload: {} },
  invoice_processing:  { event_type: 'invoice_received',          payload: {} },
  ai_accountant:       { event_type: 'transaction_posted',        payload: { transaction_ids: [] } },
  receipt_processing:  { event_type: 'receipt_processing_run',    payload: {} },
}
