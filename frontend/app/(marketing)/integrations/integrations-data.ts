export type IntegrationStatus = 'available' | 'coming_soon'

export interface Integration {
  name: string
  desc: string
  status: IntegrationStatus
}

export const INTEGRATIONS: Record<string, Integration[]> = {
  Accounting: [
    { name: 'Xero', desc: 'Sync bills, invoices, and payments', status: 'available' },
    { name: 'QuickBooks', desc: 'Full AP/AR sync and ledger updates', status: 'available' },
    { name: 'FreshBooks', desc: 'Invoice and payment sync', status: 'available' },
    { name: 'Sage', desc: 'Accounting and payroll data', status: 'coming_soon' },
    { name: 'Codat', desc: 'Unified accounting data API', status: 'coming_soon' },
  ],
  Banking: [
    { name: 'Plaid', desc: 'Bank feeds, balances, transactions (US)', status: 'available' },
    { name: 'TrueLayer', desc: 'Open banking data (UK/EU)', status: 'available' },
    { name: 'Mono', desc: 'Open banking data (Africa)', status: 'available' },
  ],
  Payments: [
    { name: 'Stripe', desc: 'Revenue, payouts, and charges', status: 'available' },
    { name: 'GoCardless', desc: 'Direct debit and bank payments', status: 'available' },
    { name: 'Adyen', desc: 'Global payment processing', status: 'available' },
    { name: 'Wise', desc: 'International transfers', status: 'available' },
    { name: 'Square', desc: 'Point of sale and invoicing', status: 'available' },
  ],
  ERP: [
    { name: 'NetSuite', desc: 'Full ERP sync (Enterprise)', status: 'available' },
    { name: 'SAP', desc: 'Enterprise financials (Enterprise)', status: 'available' },
    { name: 'Microsoft Dynamics 365', desc: 'ERP and CRM (Enterprise)', status: 'available' },
  ],
  'Document & Email': [
    { name: 'Gmail', desc: 'Invoice ingestion from email', status: 'available' },
    { name: 'Outlook', desc: 'Invoice ingestion from email', status: 'available' },
    { name: 'Google Drive', desc: 'Document storage and ingestion', status: 'available' },
    { name: 'Dropbox', desc: 'Document storage', status: 'coming_soon' },
    { name: 'OneDrive', desc: 'Document storage', status: 'coming_soon' },
  ],
}
