export interface Member {
  id: string
  email: string
  role: string
  joined_at: string
  is_self: boolean
}

export interface Invitation {
  id: string
  email: string
  role: string
  sent_at: string
}

export const ROLE_COLORS: Record<string, string> = {
  'org:owner':    'text-brand-green border-brand-green/30 bg-brand-green/08',
  'org:admin':    'text-[#00a8cc] border-[#00a8cc]/30 bg-[#00a8cc]/08',
  'org:approver': 'text-[#f5a623] border-[#f5a623]/30 bg-[#f5a623]/08',
  'org:viewer':   'text-brand-muted border-brand-border bg-transparent',
}

export const ROLE_LABEL: Record<string, string> = {
  'org:owner':    'owner',
  'org:admin':    'admin',
  'org:approver': 'approver',
  'org:viewer':   'viewer',
}
