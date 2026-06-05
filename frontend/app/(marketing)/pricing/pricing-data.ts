export interface PlanFeature {
  label: string
  included: boolean | string
}

export interface Plan {
  id: string
  name: string
  monthlyPrice: string
  annualPrice: string
  badge?: string
  highlight?: boolean
  features: PlanFeature[]
  cta: string
  ctaHref: string
  ctaExternal?: boolean
}

export const PLANS: Plan[] = [
  {
    id: 'starter',
    name: 'Starter',
    monthlyPrice: '£299',
    annualPrice: '£249',
    features: [
      { label: '2 AI workers', included: true },
      { label: '500 executions/month', included: true },
      { label: 'QuickBooks + Xero integrations', included: true },
      { label: 'Basic policy engine', included: true },
      { label: 'Approval queue', included: true },
      { label: 'Audit trail: 30 days retention', included: true },
      { label: 'Standalone API access', included: false },
      { label: 'Human approval API', included: false },
      { label: 'Explainability API', included: false },
      { label: 'Email support', included: true },
    ],
    cta: 'Start free trial',
    ctaHref: '/sign-up',
  },
  {
    id: 'growth',
    name: 'Growth',
    monthlyPrice: '£799',
    annualPrice: '£666',
    badge: 'Most Popular',
    highlight: true,
    features: [
      { label: '5 AI workers', included: true },
      { label: '5,000 executions/month', included: true },
      { label: 'All integrations', included: true },
      { label: 'Advanced policy engine', included: true },
      { label: 'Approval queue', included: true },
      { label: 'Audit trail: 1 year retention', included: true },
      { label: 'Standalone API (10,000 calls/month)', included: true },
      { label: 'Human approval API', included: true },
      { label: 'Explainability API', included: true },
      { label: 'Priority support', included: true },
    ],
    cta: 'Start free trial',
    ctaHref: '/sign-up',
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    monthlyPrice: 'Custom',
    annualPrice: 'Custom',
    features: [
      { label: 'Unlimited workers + executions', included: true },
      { label: 'Custom integrations', included: true },
      { label: 'Advanced policy engine', included: true },
      { label: 'Approval queue', included: true },
      { label: 'Audit trail: unlimited', included: true },
      { label: 'Standalone API (unlimited)', included: true },
      { label: 'Human approval API', included: true },
      { label: 'Explainability API', included: true },
      { label: 'SLA guarantee (99.9% uptime)', included: true },
      { label: 'Dedicated onboarding + support', included: true },
      { label: 'SOC 2 Type II compliance', included: true },
      { label: 'On-premise option', included: true },
    ],
    cta: 'Talk to Sales',
    ctaHref: 'mailto:sales@clendan.com',
    ctaExternal: true,
  },
]

export type CellValue = true | false | string

export interface ComparisonRow {
  feature: string
  starter: CellValue
  growth: CellValue
  enterprise: CellValue
}

export const COMPARISON: ComparisonRow[] = [
  { feature: 'AI Workers', starter: '2', growth: '5', enterprise: 'Unlimited' },
  { feature: 'Executions/month', starter: '500', growth: '5,000', enterprise: 'Unlimited' },
  { feature: 'Integrations', starter: 'Xero, QuickBooks', growth: 'All', enterprise: 'All + Custom' },
  { feature: 'Standalone APIs', starter: false, growth: '10,000 calls/mo', enterprise: 'Unlimited' },
  { feature: 'Audit Trail', starter: '30 days', growth: '1 year', enterprise: 'Unlimited' },
  { feature: 'Human Approval API', starter: false, growth: true, enterprise: true },
  { feature: 'SLA', starter: false, growth: false, enterprise: '99.9% uptime' },
  { feature: 'SOC 2', starter: false, growth: false, enterprise: true },
  { feature: 'Support', starter: 'Email', growth: 'Priority', enterprise: 'Dedicated' },
]
