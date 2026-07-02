export const TEST_PAYLOADS: Record<string, { event_type: string; payload: Record<string, unknown> }> = {
  reconciliation:      { event_type: 'reconciliation_run',         payload: { period_days: 30 } },
  document_intelligence: { event_type: 'document_received',        payload: { document_type: 'invoice' } },
  spend_control:       { event_type: 'spend_control_run',          payload: { transaction_ids: [] } },
  ar_collections:      { event_type: 'ar_collections_run',         payload: {} },
  risk_compliance:     { event_type: 'risk_compliance_run',        payload: { transaction_ids: [], frameworks: ['AML', 'KYC'] } },
  treasury_cash:       { event_type: 'treasury_cash_run',          payload: {} },
  revenue_recognition: { event_type: 'revenue_recognition_run',    payload: { contract_type: 'subscription', amount_minor: 120000, currency: 'GBP' } },
  credit_underwriting: { event_type: 'credit_underwriting_run',    payload: { applicant_id: 'test-001', requested_amount_minor: 500000 } },
  tax_compliance:      { event_type: 'tax_compliance_run',         payload: {} },
}
