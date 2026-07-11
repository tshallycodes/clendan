import { redirect } from 'next/navigation'

// The standalone Automations catalog was removed in the operator model - the Connections page
// is now the entry point (pick a connection -> pick a task -> Clen does it). Per-tool config
// pages under /tools/<slug> still resolve.
export default function ToolsPage() {
  redirect('/dashboard/integrations')
}
