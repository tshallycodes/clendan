'use client'

import { IntegrationStatus } from './types'

export function StatusDot({ status }: { status: IntegrationStatus }) {
  if (status === 'connected') {
    return (
      <span className="relative flex h-2 w-2">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#00C853] opacity-60" />
        <span className="relative inline-flex rounded-full h-2 w-2 bg-[#00C853]" />
      </span>
    )
  }
  if (status === 'syncing' || status === 'connecting') {
    return (
      <span className="relative flex h-2 w-2">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#00a8cc] opacity-60" />
        <span className="relative inline-flex rounded-full h-2 w-2 bg-[#00a8cc]" />
      </span>
    )
  }
  if (status === 'error') {
    return <span className="inline-flex rounded-full h-2 w-2 bg-[#ff4d6d]" />
  }
  return null
}

export function StatusLabel({ status }: { status: IntegrationStatus }) {
  if (status === 'connected') {
    return <span className="text-[10px] font-body text-[#00C853] tracking-wider">CONNECTED</span>
  }
  if (status === 'syncing') {
    return <span className="text-[10px] font-body text-[#00a8cc] tracking-wider">SYNCING</span>
  }
  if (status === 'connecting') {
    return <span className="text-[10px] font-body text-[#00a8cc] tracking-wider">CONNECTING</span>
  }
  if (status === 'error') {
    return <span className="text-[10px] font-body text-[#ff4d6d] tracking-wider">ERROR</span>
  }
  return null
}

export function leftBorderClass(status: IntegrationStatus): string {
  if (status === 'connected') return 'border-l-[3px] border-l-[#00C853]'
  if (status === 'error') return 'border-l-[3px] border-l-[#ff4d6d]'
  if (status === 'syncing' || status === 'connecting') return 'border-l-[3px] border-l-[#00a8cc]'
  return ''
}
