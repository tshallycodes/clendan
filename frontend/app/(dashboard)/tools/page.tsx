import type { Metadata } from 'next'
import { getBackendToken } from '@/lib/auth'
import { apiGet } from '@/lib/api'
import { ToolsClient } from './ToolsClient'
import type { Tool } from '@/components/dashboard/tools/ToolCard'

export const metadata: Metadata = { title: 'Tools' }

export default async function ToolsPage() {
  let tools: Tool[] = []
  try {
    const token = await getBackendToken()
    if (token) {
      const res = await apiGet<{ tools: Tool[] }>('/tools', token)
      tools = res.tools ?? []
    }
  } catch { /* backend not running */ }
  return <ToolsClient deployedTools={tools} />
}
