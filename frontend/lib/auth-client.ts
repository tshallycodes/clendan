'use client'

import { useState, useEffect } from 'react'
import { useAuth } from '@clerk/nextjs'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export function useCurrentUserRole(): string {
  const { getToken } = useAuth()
  const [role, setRole] = useState('viewer')

  useEffect(() => {
    getToken().then((token) => {
      if (!token) return
      fetch(`${API}/tenants/me`, { headers: { Authorization: `Bearer ${token}` } })
        .then((r) => (r.ok ? r.json() : null))
        .then((j) => { if (j?.data?.user?.role) setRole(j.data.user.role) })
        .catch(() => {})
    })
  }, [getToken])

  return role
}

export function useCanApprove(): boolean {
  return ['owner', 'admin', 'approver'].includes(useCurrentUserRole())
}

export function useCanConfigure(): boolean {
  return ['owner', 'admin'].includes(useCurrentUserRole())
}

export function useIsOwner(): boolean {
  return useCurrentUserRole() === 'owner'
}
