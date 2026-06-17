import { getBackendToken } from '@/lib/auth'
import { apiGet } from '@/lib/api'
import { OrgNameForm } from '@/components/dashboard/settings/OrgNameForm'
import { NotificationsSection } from '@/components/dashboard/settings/NotificationsSection'
import { DangerZone } from '@/components/dashboard/settings/DangerZone'
import { IntegrationsSection } from '@/components/dashboard/settings/IntegrationsSection'
import { TeamSection } from '@/components/dashboard/settings/TeamSection'
import { InviteLinksSection } from '@/components/dashboard/settings/team/InviteLinksSection'
import { PolicySection } from '@/components/dashboard/settings/PolicySection'
import { ApiKeysSection } from '@/components/dashboard/settings/ApiKeysSection'
import { WebhooksSection } from '@/components/dashboard/settings/WebhooksSection'
import { BillingSection } from '@/components/dashboard/settings/BillingSection'
import { AnimatedPage, AnimatedSection } from '@/components/dashboard/AnimatedPage'

interface TenantData {
  tenant: { id: string; name: string; created_at: string }
  user:   { email: string; role: string }
}

export default async function SettingsPage() {
  let data: TenantData | null = null
  try {
    const token = await getBackendToken()
    if (token) data = await apiGet<TenantData>('/v1/tenants/me', token)
  } catch { /* backend not running — show empty state */ }

  const ROLE_COLORS: Record<string, string> = {
    owner:    'text-brand-green border-brand-green/30 bg-[rgba(0,200,83,0.08)]',
    admin:    'text-[#00a8cc] border-[#00a8cc]/30 bg-[rgba(0,168,204,0.08)]',
    approver: 'text-[#f5a623] border-[#f5a623]/30 bg-[rgba(245,166,35,0.08)]',
    viewer:   'text-brand-muted border-brand-border bg-transparent',
    member:   'text-brand-muted border-brand-border bg-transparent',
  }

  return (
    <AnimatedPage className="p-6 max-w-2xl space-y-10">
      <AnimatedSection>
        <div>
          <h1 className="font-heading font-bold text-2xl text-brand-text">Settings</h1>
          <p className="text-brand-muted text-xs font-mono mt-1">Manage your organisation and credentials</p>
        </div>
      </AnimatedSection>

      {/* Organisation */}
      <AnimatedSection>
        <section className="space-y-4">
          <h2 className="text-[10px] font-mono uppercase tracking-widest text-brand-muted border-b border-brand-border pb-2">Organisation</h2>
          <div className="space-y-3">
            <div>
              <p className="text-[10px] font-mono text-brand-muted mb-1.5 uppercase tracking-wide">Name</p>
              {data ? (
                <OrgNameForm initialName={data.tenant.name} />
              ) : (
                <p className="text-xs font-mono text-brand-muted">Backend unavailable</p>
              )}
            </div>
            <div>
              <p className="text-[10px] font-mono text-brand-muted mb-1.5 uppercase tracking-wide">Tenant ID</p>
              <div className="flex items-center gap-2">
                <code className="text-xs font-mono text-brand-text bg-brand-bg border border-brand-border rounded-sm px-3 py-2">
                  {data?.tenant.id ?? '—'}
                </code>
                <span className="text-[10px] font-mono text-brand-muted">use as X-Tenant-ID in API calls</span>
              </div>
            </div>
            <div>
              <p className="text-[10px] font-mono text-brand-muted mb-1.5 uppercase tracking-wide">Created</p>
              <p className="text-xs font-mono text-brand-text">
                {data ? new Date(data.tenant.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' }) : '—'}
              </p>
            </div>
          </div>
        </section>
      </AnimatedSection>

      {/* Account */}
      <AnimatedSection>
        <section className="space-y-4">
          <h2 className="text-[10px] font-mono uppercase tracking-widest text-brand-muted border-b border-brand-border pb-2">Your Account</h2>
          <div className="space-y-3">
            <div>
              <p className="text-[10px] font-mono text-brand-muted mb-1.5 uppercase tracking-wide">Email</p>
              <p className="text-xs font-mono text-brand-text">{data?.user.email ?? '—'}</p>
            </div>
            <div>
              <p className="text-[10px] font-mono text-brand-muted mb-1.5 uppercase tracking-wide">Role</p>
              {data ? (
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded-sm border ${ROLE_COLORS[data.user.role.toLowerCase()] ?? ROLE_COLORS.member}`}>
                  {data.user.role.charAt(0).toUpperCase() + data.user.role.slice(1).toLowerCase()}
                </span>
              ) : <p className="text-xs font-mono text-brand-muted">—</p>}
            </div>
          </div>
        </section>
      </AnimatedSection>

      {/* Team */}
      <AnimatedSection>
        <section className="space-y-4">
          <h2 className="text-[10px] font-mono uppercase tracking-widest text-brand-muted border-b border-brand-border pb-2">Team</h2>
          <TeamSection />
        </section>
      </AnimatedSection>

      {/* Invite Links */}
      <AnimatedSection>
        <section className="space-y-4">
          <h2 className="text-[10px] font-mono uppercase tracking-widest text-brand-muted border-b border-brand-border pb-2">Invite Links</h2>
          <InviteLinksSection />
        </section>
      </AnimatedSection>

      {/* Integrations */}
      <AnimatedSection>
        <section className="space-y-4">
          <div className="border-b border-brand-border pb-2 flex items-baseline justify-between">
            <h2 className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Integrations</h2>
            <p className="text-[10px] font-mono text-brand-muted">External systems connected to your tools</p>
          </div>
          <IntegrationsSection />
        </section>
      </AnimatedSection>

      {/* Policy & Approvals */}
      <AnimatedSection>
        <section className="space-y-4">
          <div className="border-b border-brand-border pb-2 flex items-baseline justify-between">
            <h2 className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Policy &amp; Approvals</h2>
            <p className="text-[10px] font-mono text-brand-muted">Autonomy level and thresholds per tool</p>
          </div>
          <PolicySection />
        </section>
      </AnimatedSection>

      {/* API Keys */}
      <AnimatedSection>
        <section className="space-y-4">
          <div className="border-b border-brand-border pb-2 flex items-baseline justify-between">
            <h2 className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">API Keys</h2>
            <p className="text-[10px] font-mono text-brand-muted">For external systems connecting to Clendan</p>
          </div>
          <ApiKeysSection />
        </section>
      </AnimatedSection>

      {/* Webhooks */}
      <AnimatedSection>
        <section className="space-y-4">
          <div className="border-b border-brand-border pb-2 flex items-baseline justify-between">
            <h2 className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Webhooks</h2>
            <p className="text-[10px] font-mono text-brand-muted">Receive real-time events from your tools</p>
          </div>
          <WebhooksSection />
        </section>
      </AnimatedSection>

      {/* Notifications */}
      <AnimatedSection>
        <section className="space-y-4">
          <h2 className="text-[10px] font-mono uppercase tracking-widest text-brand-muted border-b border-brand-border pb-2">Notifications</h2>
          <NotificationsSection />
        </section>
      </AnimatedSection>

      {/* Billing */}
      <AnimatedSection>
        <section className="space-y-4">
          <h2 className="text-[10px] font-mono uppercase tracking-widest text-brand-muted border-b border-brand-border pb-2">Billing</h2>
          <BillingSection />
        </section>
      </AnimatedSection>

      {/* Danger Zone */}
      <AnimatedSection>
        <section className="space-y-4">
          <h2 className="text-[10px] font-mono uppercase tracking-widest text-[#ff4d6d] border-b border-[#ff4d6d]/20 pb-2">Danger Zone</h2>
          <DangerZone />
        </section>
      </AnimatedSection>
    </AnimatedPage>
  )
}
