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
  owner:    'text-brand-green border-brand-green/30 bg-[rgba(0,200,83,0.08)]',
  admin:    'text-[#00a8cc] border-[#00a8cc]/30 bg-[rgba(0,168,204,0.08)]',
  approver: 'text-[#f5a623] border-[#f5a623]/30 bg-[rgba(245,166,35,0.08)]',
  viewer:   'text-brand-muted border-brand-border bg-transparent',
}

export const ROLE_LABEL: Record<string, string> = {
  owner:    'Owner',
  admin:    'Admin',
  approver: 'Approver',
  viewer:   'Viewer',
}
