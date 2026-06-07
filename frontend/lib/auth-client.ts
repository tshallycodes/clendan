'use client'

import { useOrganization } from '@clerk/nextjs'

export function useRole(): string {
  const { membership } = useOrganization()
  return (membership?.role ?? 'org:viewer') as string
}

export function useCanApprove(): boolean {
  const role = useRole()
  return ['org:owner', 'org:admin', 'org:approver'].includes(role)
}

export function useCanConfigure(): boolean {
  const role = useRole()
  return ['org:owner', 'org:admin'].includes(role)
}

export function useIsOwner(): boolean {
  const role = useRole()
  return role === 'org:owner'
}
