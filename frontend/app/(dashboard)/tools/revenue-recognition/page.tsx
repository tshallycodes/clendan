import type { Metadata } from 'next'
import { getBackendToken } from '@/lib/auth'
import { apiGet } from '@/lib/api'
import { slugToTool } from '../tools-data'
import { GenericToolClient } from '../[slug]/GenericToolClient'
import type { Tool } from '@/components/dashboard/tools/ToolCard'

const SLUG = 'revenue-recognition'

export const metadata: Metadata = { title: 'Revenue Recognition' }

export default async function RevenueRecognitionPage() {
  const tool = slugToTool(SLUG)!
  let deployed: Tool | null = null

  try {
    const token = await getBackendToken()
    if (token) {
      const res = await apiGet<{ tools: Tool[] }>('/tools', token)
      const tools = res.tools ?? []
      deployed = tools.find((w) => w.type === tool.type) ?? null
    }
  } catch { /* backend not running */ }

  return <GenericToolClient tool={tool} deployed={deployed} />
}
