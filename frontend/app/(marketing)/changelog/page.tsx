'use client'

import { useState } from 'react'

const ENTRIES = [
  {
    date: '2026-06-05',
    version: 'v0.3.0',
    category: 'New Feature',
    title: 'Tool Management & API Keys',
    body: 'Deploy and configure AI tools directly from the dashboard. Generate API keys for programmatic access. Full tool CRUD with autonomy level and policy threshold configuration.',
  },
  {
    date: '2026-06-04',
    version: 'v0.2.0',
    category: 'New Feature',
    title: 'Developer API Docs & Onboarding Flow',
    body: 'Interactive Swagger UI at /docs. Developer API reference page with code examples in Python and TypeScript. Onboarding flow for new workspaces.',
  },
  {
    date: '2026-06-02',
    version: 'v0.1.0',
    category: 'New Feature',
    title: 'Platform Foundation',
    body: 'Multi-tenant PostgreSQL with row-level security. Invoice Processing Tool, AI Accountant Tool, Receipt Processing Tool. Full audit trail, approval queue, and policy engine.',
  },
]

const CATEGORY_COLOR: Record<string, string> = {
  'New Feature': '#00C853',
  Improvement: '#00a8cc',
  Fix: '#f5a623',
}

const CATEGORY_BG: Record<string, string> = {
  'New Feature': 'rgba(0,200,83,0.08)',
  Improvement: 'rgba(0,168,204,0.08)',
  Fix: 'rgba(245,166,35,0.08)',
}

const CATEGORY_BORDER: Record<string, string> = {
  'New Feature': 'rgba(0,200,83,0.2)',
  Improvement: 'rgba(0,168,204,0.2)',
  Fix: 'rgba(245,166,35,0.2)',
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-GB', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

function SubscribeForm() {
  const [value, setValue] = useState('')
  const [submitted, setSubmitted] = useState(false)

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (value.trim()) setSubmitted(true)
  }

  return (
    <div className="border-t border-brand-border pt-16 mt-16">
      <div className="max-w-md mx-auto text-center">
        <p
          className="font-heading font-bold text-xl mb-2"
          style={{ fontFamily: 'var(--font-heading)' }}
        >
          Get notified of new releases
        </p>
        <p className="font-body text-xs text-brand-secondary mb-6">
          No spam. Just the changelog, delivered to your inbox.
        </p>
        {submitted ? (
          <p className="font-body text-sm text-brand-green">
            You&apos;re on the list.
          </p>
        ) : (
          <form onSubmit={handleSubmit} className="flex gap-2">
            <input
              type="email"
              placeholder="you@company.com"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              required
              className="flex-1 bg-brand-bg border border-brand-border rounded-sm px-3 py-2 font-body text-sm text-brand-text placeholder:text-brand-muted focus:outline-none focus:border-brand-green transition-colors"
            />
            <button
              type="submit"
              className="rounded-sm px-4 py-2 text-sm font-body font-medium transition-colors hover:bg-[#00a844]"
              style={{ background: '#00C853', color: '#000' }}
            >
              Subscribe
            </button>
          </form>
        )}
      </div>
    </div>
  )
}

export default function ChangelogPage() {
  return (
    <div className="bg-brand-bg text-brand-text">
      {/* Hero */}
      <section className="max-w-6xl mx-auto px-6 md:px-8 pt-20 pb-14">
        <p className="font-body text-[10px] uppercase tracking-widest text-brand-muted mb-4">
          Changelog
        </p>
        <h1
          className="text-4xl md:text-5xl font-heading font-extrabold leading-tight mb-4"
          style={{ fontFamily: 'var(--font-heading)' }}
        >
          What&apos;s New in Clendan
        </h1>
        <p className="font-body text-sm text-brand-secondary max-w-xl">
          Every update, fix, and new feature — in order.
        </p>
      </section>

      {/* Entries */}
      <section className="max-w-3xl mx-auto px-6 md:px-8 pb-8">
        <div className="flex flex-col gap-0">
          {ENTRIES.map((entry, i) => (
            <div
              key={entry.version}
              className="flex gap-8 py-10"
              style={{ borderTop: i > 0 ? '1px solid #1a2a1a' : 'none' }}
            >
              {/* Date column */}
              <div className="hidden md:flex flex-col items-end shrink-0 w-36 pt-1 gap-2">
                <span
                  className="font-body text-[10px] uppercase tracking-widest px-2 py-0.5 rounded-sm"
                  style={{
                    background: 'rgba(0,200,83,0.08)',
                    color: '#00C853',
                    border: '1px solid rgba(0,200,83,0.2)',
                  }}
                >
                  {formatDate(entry.date)}
                </span>
                <span className="font-body text-[10px] text-brand-muted">{entry.version}</span>
              </div>

              {/* Content */}
              <div className="flex-1 flex flex-col gap-3">
                <div className="flex flex-wrap items-center gap-2">
                  {/* Mobile date */}
                  <span
                    className="md:hidden font-body text-[10px] uppercase tracking-widest px-2 py-0.5 rounded-sm"
                    style={{
                      background: 'rgba(0,200,83,0.08)',
                      color: '#00C853',
                      border: '1px solid rgba(0,200,83,0.2)',
                    }}
                  >
                    {formatDate(entry.date)}
                  </span>
                  <span className="md:hidden font-body text-[10px] text-brand-muted">
                    {entry.version}
                  </span>
                  <span
                    className="font-body text-[10px] uppercase tracking-widest px-2 py-0.5 rounded-sm"
                    style={{
                      background: CATEGORY_BG[entry.category],
                      color: CATEGORY_COLOR[entry.category],
                      border: `1px solid ${CATEGORY_BORDER[entry.category]}`,
                    }}
                  >
                    {entry.category}
                  </span>
                </div>
                <h2
                  className="font-heading font-bold text-lg"
                  style={{ fontFamily: 'var(--font-heading)' }}
                >
                  {entry.title}
                </h2>
                <p className="font-body text-sm text-brand-secondary leading-relaxed">
                  {entry.body}
                </p>
              </div>
            </div>
          ))}
        </div>

        <SubscribeForm />
      </section>
    </div>
  )
}
