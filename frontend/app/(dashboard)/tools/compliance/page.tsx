import { getBackendToken } from '@/lib/auth'
import { apiGet } from '@/lib/api'
import { slugToTool } from '../tools-data'
import { GenericToolClient } from '../[slug]/GenericToolClient'
import type { Tool } from '@/components/dashboard/tools/ToolCard'

const SLUG = 'compliance'

export default async function CompliancePage() {
  const tool = slugToTool(SLUG)!

  let tools: Tool[] = []

  try {
    const token = await getBackendToken()
    if (token) {
      const res = await apiGet<{ tools: Tool[] }>('/v1/tools', token)
      tools = res.tools ?? []
    }
  } catch { /* backend not running */ }

  const deployed = tools.find((w) => w.type === tool.type) ?? null
  return <GenericToolClient tool={tool} deployed={deployed} />
}
