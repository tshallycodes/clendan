'use client'

const ROLES = ['Admin', 'Approver', 'Viewer'] as const
export type Role = typeof ROLES[number]

export interface Invitation {
  email: string
  role: Role
}

interface InviteRowProps {
  invite: Invitation
  onChange: (next: Invitation) => void
  onRemove: () => void
  showRemove: boolean
}

const INPUT = 'flex-1 bg-brand-bg border border-brand-border focus:border-brand-green rounded-sm px-3 py-2 text-xs font-mono text-brand-text placeholder:text-brand-muted outline-none transition-colors'
const SELECT = 'bg-brand-bg border border-brand-border focus:border-brand-green rounded-sm px-2 py-2 text-xs font-mono text-brand-text outline-none transition-colors'

export function InviteRow({ invite, onChange, onRemove, showRemove }: InviteRowProps) {
  return (
    <div className="flex items-center gap-2">
      <input
        type="email"
        value={invite.email}
        onChange={(e) => onChange({ ...invite, email: e.target.value })}
        placeholder="colleague@company.com"
        className={INPUT}
      />
      <select
        value={invite.role}
        onChange={(e) => onChange({ ...invite, role: e.target.value as Role })}
        className={SELECT}
      >
        {ROLES.map((r) => <option key={r}>{r}</option>)}
      </select>
      {showRemove && (
        <button
          type="button"
          onClick={onRemove}
          className="text-brand-muted hover:text-brand-danger text-xs font-mono transition-colors px-1"
          aria-label="Remove"
        >
          ✕
        </button>
      )}
    </div>
  )
}
