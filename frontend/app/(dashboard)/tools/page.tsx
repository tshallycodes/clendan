import type { Metadata } from 'next'
import { getBackendToken } from '@/lib/auth'
import { apiGet } from '@/lib/api'
import { ToolsClient, type WorkflowConnection } from './ToolsClient'
import type { Tool } from '@/components/dashboard/tools/ToolCard'

export const metadata: Metadata = { title: 'Tools' }

export default async function ToolsPage() {
  let tools: Tool[] = []
  let connections: WorkflowConnection[] = []
  try {
    const token = await getBackendToken()
    if (token) {
      const [toolsRes, connRes] = await Promise.allSettled([
        apiGet<{ tools: Tool[] }>('/tools', token),
        apiGet<{ connections: WorkflowConnection[] }>('/workflows/connections', token),
      ])
      if (toolsRes.status === 'fulfilled') tools = toolsRes.value.tools ?? []
      if (connRes.status === 'fulfilled') connections = connRes.value.connections ?? []
    }
  } catch { /* backend not running */ }
  return <ToolsClient deployedTools={tools} connections={connections} />
}
