import type { Metadata } from 'next'
import { getBackendToken } from '@/lib/auth'
import { apiGet } from '@/lib/api'
import { slugToTool } from '../tools-data'
import { GenericToolClient } from '../[slug]/GenericToolClient'
import type { Tool } from '@/components/dashboard/tools/ToolCard'

const SLUG = 'payment-runs'

export const metadata: Metadata = { title: 'Payment Runs' }

export default async function PaymentRunsPage() {
  const tool = slugToTool(SLUG)!
  let deployed: Tool | null = null

  try {
    const token = await getBackendToken()
    if (token) {
      const res = await apiGet<{ tools: Tool[] }>('/v1/tools', token)
      const tools = res.tools ?? []
      deployed = tools.find((w) => w.type === tool.type) ?? null
    }
  } catch { /* backend not running */ }

  return <GenericToolClient tool={tool} deployed={deployed} />
}
