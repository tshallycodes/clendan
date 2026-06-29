import type { Metadata } from 'next'
import { notFound } from 'next/navigation'
import { getBackendToken } from '@/lib/auth'
import { apiGet } from '@/lib/api'
import { slugToTool } from '../tools-data'
import { GenericToolClient } from './GenericToolClient'
import type { Tool } from '@/components/dashboard/tools/ToolCard'

interface PageProps {
  params: Promise<{ slug: string }>
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params
  const tool = slugToTool(slug)
  return { title: tool?.name ?? 'Tool' }
}

export default async function ToolSlugPage({ params }: PageProps) {
  const { slug } = await params
  const tool = slugToTool(slug)
  if (!tool) notFound()

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
