import type { Metadata } from 'next'
import Link from 'next/link'
import { getBackendToken } from '@/lib/auth'
import { apiGet } from '@/lib/api'
import { OrgNameForm } from '@/components/dashboard/settings/OrgNameForm'
import { NotificationsSection } from '@/components/dashboard/settings/NotificationsSection'
import { DangerZone } from '@/components/dashboard/settings/DangerZone'
import { IntegrationsSection } from '@/components/dashboard/settings/IntegrationsSection'
import { TeamSection } from '@/components/dashboard/settings/TeamSection'
import { InviteLinksSection } from '@/components/dashboard/settings/team/InviteLinksSection'
import { PolicySection } from '@/components/dashboard/settings/PolicySection'
import { BillingSection } from '@/components/dashboard/settings/BillingSection'
import { CurrencySelector } from '@/components/dashboard/settings/CurrencySelector'
import { TimezoneSelector } from '@/components/dashboard/settings/TimezoneSelector'
import { AnimatedPage, AnimatedSection } from '@/components/dashboard/AnimatedPage'

export const metadata: Metadata = { title: 'Settings' }

interface TenantData {
  tenant: { id: string; name: string; created_at: string }
  user:   { email: string; role: string }
}

export default async function SettingsPage() {
  let data: TenantData | null = null
  try {
    const token = await getBackendToken()
    if (token) data = await apiGet<TenantData>('/tenants/me', token)
  } catch { /* backend not running - show empty state */ }

  const ROLE_COLORS: Record<string, string> = {
    owner:    'text-brand-green border-brand-green/30 bg-[rgba(0,200,83,0.08)]',
    admin:    'text-[#00a8cc] border-[#00a8cc]/30 bg-[rgba(0,168,204,0.08)]',
    approver: 'text-[#f5a623] border-[#f5a623]/30 bg-[rgba(245,166,35,0.08)]',
    viewer:   'text-brand-muted border-brand-border bg-transparent',
    member:   'text-brand-muted border-brand-border bg-transparent',
  }

  return (
    <AnimatedPage className="p-6 space-y-8">

      {/* Header */}
      <AnimatedSection>
        <div>
          <h1 className="font-heading font-bold text-2xl text-brand-text">Settings</h1>
          <p className="text-brand-muted text-xs font-body mt-1">Manage your organisation, team, and credentials</p>
        </div>
      </AnimatedSection>

      {/* Two-column grid */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-x-10 gap-y-10 items-start">

        {/* ── Left column: identity & preferences ── */}
        <div className="space-y-10">

          {/* Organisation */}
          <AnimatedSection>
            <section className="space-y-4">
              <h2 className="text-[11px] font-body uppercase tracking-widest text-brand-muted border-b border-brand-border pb-2">Organisation</h2>
              <div className="space-y-3">
                <div>
                  <p className="text-[11px] font-body text-brand-muted mb-1.5 uppercase tracking-wide">Name</p>
                  {data ? <OrgNameForm initialName={data.tenant.name} /> : <p className="text-xs font-body text-brand-muted">Backend unavailable</p>}
                </div>
                <div>
                  <p className="text-[11px] font-body text-brand-muted mb-1.5 uppercase tracking-wide">Tenant ID</p>
                  <div className="flex items-center gap-2 flex-wrap">
                    <code className="text-xs font-body text-brand-text bg-brand-bg border border-brand-border rounded-sm px-3 py-2">
                      {data?.tenant.id ?? '-'}
                    </code>
                    <span className="text-[11px] font-body text-brand-muted">use as X-Tenant-ID in API calls</span>
                  </div>
                </div>
                <div>
                  <p className="text-[11px] font-body text-brand-muted mb-1.5 uppercase tracking-wide">Created</p>
                  <p className="text-xs font-body text-brand-text">
                    {data ? new Date(data.tenant.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' }) : '-'}
                  </p>
                </div>
              </div>
            </section>
          </AnimatedSection>

          {/* Account */}
          <AnimatedSection>
            <section className="space-y-4">
              <h2 className="text-[11px] font-body uppercase tracking-widest text-brand-muted border-b border-brand-border pb-2">Your Account</h2>
              <div className="space-y-3">
                <div>
                  <p className="text-[11px] font-body text-brand-muted mb-1.5 uppercase tracking-wide">Email</p>
                  <p className="text-xs font-body text-brand-text">{data?.user.email ?? '-'}</p>
                </div>
                <div>
                  <p className="text-[11px] font-body text-brand-muted mb-1.5 uppercase tracking-wide">Role</p>
                  {data ? (
                    <span className={`text-[11px] font-body px-2 py-0.5 rounded-sm border ${ROLE_COLORS[data.user.role.toLowerCase()] ?? ROLE_COLORS.member}`}>
                      {data.user.role.charAt(0).toUpperCase() + data.user.role.slice(1).toLowerCase()}
                    </span>
                  ) : <p className="text-xs font-body text-brand-muted">-</p>}
                </div>
              </div>
            </section>
          </AnimatedSection>

          {/* Display Currency */}
          <AnimatedSection>
            <section className="space-y-4">
              <h2 className="text-[11px] font-body uppercase tracking-widest text-brand-muted border-b border-brand-border pb-2">Display Currency</h2>
              <div className="space-y-2">
                <p className="text-[11px] font-body text-brand-muted uppercase tracking-wide">Preferred currency</p>
                <CurrencySelector />
                <p className="text-[11px] font-body text-brand-muted leading-relaxed">
                  All monetary values across the dashboard are displayed in this currency. Amounts are converted from their native currency at read time - stored values are never modified.
                </p>
              </div>
            </section>
          </AnimatedSection>

          {/* Timezone */}
          <AnimatedSection>
            <section className="space-y-4">
              <h2 className="text-[11px] font-body uppercase tracking-widest text-brand-muted border-b border-brand-border pb-2">Timezone</h2>
              <div className="space-y-2">
                <p className="text-[11px] font-body text-brand-muted uppercase tracking-wide">Organisation timezone</p>
                <TimezoneSelector />
                <p className="text-[11px] font-body text-brand-muted leading-relaxed">
                  Used for scheduling automated tool runs (daily reconciliation, weekly payment runs, etc.) and displaying timestamps across the dashboard.
                </p>
              </div>
            </section>
          </AnimatedSection>

          {/* Notifications */}
          <AnimatedSection>
            <section className="space-y-4">
              <h2 className="text-[11px] font-body uppercase tracking-widest text-brand-muted border-b border-brand-border pb-2">Notifications</h2>
              <NotificationsSection />
            </section>
          </AnimatedSection>

          {/* Billing */}
          <AnimatedSection>
            <section className="space-y-4">
              <h2 className="text-[11px] font-body uppercase tracking-widest text-brand-muted border-b border-brand-border pb-2">Billing</h2>
              <BillingSection />
            </section>
          </AnimatedSection>

          {/* Developer */}
          <AnimatedSection>
            <section className="space-y-4">
              <h2 className="text-[11px] font-body uppercase tracking-widest text-brand-muted border-b border-brand-border pb-2">Developer</h2>
              <div className="divide-y divide-brand-border border border-brand-border rounded-sm">
                <Link href="/developer" className="flex items-center justify-between px-3 py-2.5 hover:bg-brand-elevated transition-colors group">
                  <div>
                    <p className="text-xs font-body text-brand-text">API playground &amp; keys</p>
                    <p className="text-[11px] font-body text-brand-muted mt-0.5">Test endpoints and manage API keys</p>
                  </div>
                  <span className="text-brand-muted group-hover:text-brand-text transition-colors text-xs">&rarr;</span>
                </Link>
                <Link href="/api" className="flex items-center justify-between px-3 py-2.5 hover:bg-brand-elevated transition-colors group">
                  <div>
                    <p className="text-xs font-body text-brand-text">API reference</p>
                    <p className="text-[11px] font-body text-brand-muted mt-0.5">Full endpoint documentation</p>
                  </div>
                  <span className="text-brand-muted group-hover:text-brand-text transition-colors text-xs">&rarr;</span>
                </Link>
              </div>
            </section>
          </AnimatedSection>

          {/* Danger Zone */}
          <AnimatedSection>
            <section className="space-y-4">
              <h2 className="text-[11px] font-body uppercase tracking-widest text-[#ff4d6d] border-b border-[#ff4d6d]/20 pb-2">Danger Zone</h2>
              <DangerZone />
            </section>
          </AnimatedSection>

        </div>

        {/* ── Right column: team & connections ── */}
        <div className="space-y-10">

          {/* Team */}
          <AnimatedSection>
            <section className="space-y-4">
              <h2 className="text-[11px] font-body uppercase tracking-widest text-brand-muted border-b border-brand-border pb-2">Team</h2>
              <TeamSection />
            </section>
          </AnimatedSection>

          {/* Invite Links */}
          <AnimatedSection>
            <section className="space-y-4">
              <h2 className="text-[11px] font-body uppercase tracking-widest text-brand-muted border-b border-brand-border pb-2">Invite Links</h2>
              <InviteLinksSection />
            </section>
          </AnimatedSection>

          {/* Integrations */}
          <AnimatedSection>
            <section className="space-y-4">
              <div className="border-b border-brand-border pb-2 flex items-baseline justify-between">
                <h2 className="text-[11px] font-body uppercase tracking-widest text-brand-muted">Integrations</h2>
                <p className="text-[11px] font-body text-brand-muted">Connected external systems</p>
              </div>
              <IntegrationsSection />
            </section>
          </AnimatedSection>

          {/* Policy & Approvals */}
          <AnimatedSection>
            <section className="space-y-4">
              <div className="border-b border-brand-border pb-2 flex items-baseline justify-between">
                <h2 className="text-[11px] font-body uppercase tracking-widest text-brand-muted">Policy &amp; Approvals</h2>
                <p className="text-[11px] font-body text-brand-muted">Autonomy per tool</p>
              </div>
              <PolicySection />
            </section>
          </AnimatedSection>

        </div>
      </div>
    </AnimatedPage>
  )
}
