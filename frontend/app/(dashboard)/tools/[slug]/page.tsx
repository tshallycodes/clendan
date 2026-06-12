import { notFound } from 'next/navigation'
import { getBackendToken } from '@/lib/auth'
import { apiGet } from '@/lib/api'
import { slugToTool } from '../tools-data'
import { GenericToolClient } from './GenericToolClient'
import type { Tool } from '@/components/dashboard/tools/ToolCard'

interface PageProps {
  params: { slug: string }
}

export default async function ToolSlugPage({ params }: PageProps) {
  const tool = slugToTool(params.slug)
  if (!tool) notFound()

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
