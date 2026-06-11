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
    { name: 'FreshBooks', desc: 'Invoice and payment sync', status: 'coming_soon' },
    { name: 'Sage', desc: 'Accounting and payroll data', status: 'coming_soon' },
    { name: 'Codat', desc: 'Unified accounting data API', status: 'coming_soon' },
  ],
  Banking: [
    { name: 'Plaid', desc: 'Bank feeds, balances, transactions', status: 'available' },
    { name: 'TrueLayer', desc: 'Open banking data (UK/EU)', status: 'coming_soon' },
  ],
  Payments: [
    { name: 'Stripe', desc: 'Revenue, payouts, and charges', status: 'coming_soon' },
    { name: 'GoCardless', desc: 'Direct debit and bank payments', status: 'coming_soon' },
    { name: 'Adyen', desc: 'Global payment processing', status: 'coming_soon' },
    { name: 'Wise', desc: 'International transfers', status: 'coming_soon' },
  ],
  ERP: [
    { name: 'NetSuite', desc: 'Full ERP sync (Enterprise)', status: 'coming_soon' },
    { name: 'SAP', desc: 'Enterprise financials (Enterprise)', status: 'coming_soon' },
    { name: 'Microsoft Dynamics', desc: 'ERP and CRM (Enterprise)', status: 'coming_soon' },
  ],
  CRM: [
    { name: 'Salesforce', desc: 'Customer and contract data', status: 'coming_soon' },
    { name: 'HubSpot', desc: 'Deal and revenue data', status: 'coming_soon' },
  ],
}
