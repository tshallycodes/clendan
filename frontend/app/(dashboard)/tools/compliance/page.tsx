import { getBackendToken } from '@/lib/auth'
import { apiGet } from '@/lib/api'
import { slugToTool } from '../tools-data'
import { GenericToolClient } from '../[slug]/GenericToolClient'
import type { Tool } from '@/components/dashboard/tools/ToolCard'
import type { Execution } from '@/components/dashboard/tools/ToolDetail'

const SLUG = 'compliance'

export default async function CompliancePage() {
  const tool = slugToTool(SLUG)!

  let tools: Tool[] = []
  let executions: Execution[] = []

  try {
    const token = await getBackendToken()
    if (token) {
      const res = await apiGet<{ tools: Tool[] }>('/v1/tools', token)
      tools = res.tools ?? []
      const deployed = tools.find((w) => w.type === tool.type)
      if (deployed) {
        const exRes = await apiGet<{ executions: Execution[] }>(
          `/v1/dashboard/executions?tool_id=${deployed.id}&limit=20`, token
        )
        executions = exRes.executions ?? []
      }
    }
  } catch { /* backend not running */ }

  const deployed = tools.find((w) => w.type === tool.type) ?? null
  return <GenericToolClient tool={tool} deployed={deployed} executions={executions} />
}
