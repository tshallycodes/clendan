import { getBackendToken } from '@/lib/auth'
import { apiGet } from '@/lib/api'
import { ToolsClient } from './ToolsClient'
import type { Tool } from '@/components/dashboard/tools/ToolCard'

export default async function ToolsPage() {
  let tools: Tool[] = []
  try {
    const token = await getBackendToken()
    if (token) {
      const res = await apiGet<{ tools: Tool[] }>('/v1/tools', token)
      tools = res.tools ?? []
    }
  } catch { /* backend not running */ }
  return <ToolsClient deployedTools={tools} />
}
