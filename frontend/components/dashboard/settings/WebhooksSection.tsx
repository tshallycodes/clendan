'use client'

import Link from 'next/link'

const WEBHOOK_SNIPPET = `POST /webhooks
Authorization: ck_live_...
Content-Type: application/json

{
  "url": "https://your-app.com/webhooks/clendan",
  "events": [
    "tool.executed",
    "tool.approval_required",
    "tool.policy_blocked"
  ]
}`

export function WebhooksSection() {
  return (
    <div className="space-y-4">
      <p className="text-xs font-body text-brand-text">
        Register a URL to receive real-time events when your tools execute, require approval, or are blocked.
      </p>

      <pre className="bg-brand-bg border border-brand-border rounded-sm px-4 py-3 font-body text-xs text-brand-text whitespace-pre overflow-x-auto">
        {WEBHOOK_SNIPPET}
      </pre>

      <p className="text-xs font-body text-brand-secondary">
        Register and manage webhooks via the API.{' '}
        <a
          href="https://docs.clendan.com/api-reference"
          target="_blank"
          rel="noopener noreferrer"
          className="text-brand-text underline underline-offset-2 hover:text-[#00C853] transition-colors"
        >
          API Reference
        </a>{' '}
        for the full event list.
      </p>

      <Link
        href="/developer"
        className="inline-flex text-xs font-body text-brand-text hover:text-[#00C853] transition-colors"
      >
        Get your API key →
      </Link>
    </div>
  )
}
